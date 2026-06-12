"""Feishu Wiki uploader - creates wiki nodes and populates them with document content."""

from typing import Optional

from src.feishu_client import FeishuClient
from src.markdown_to_blocks import markdown_to_feishu_blocks


class FeishuUploader:
    """Creates a wiki node and populates it with document content."""

    def __init__(self, config: dict):
        self.config = config
        self.client = FeishuClient(config)
        self.space_id = config["feishu"]["wiki_space_id"]
        self.parent_node_token = config["feishu"].get("parent_node_token", "")
        self.source_parent_node_tokens = config["feishu"].get("source_parent_node_tokens", {})

    def upload(self, title: str, markdown_content: str, source_name: Optional[str] = None) -> str:
        """
        Create a wiki node containing a docx document with the given content.
        Returns the wiki URL.
        """
        # Step 1: Create wiki node (obj_type="docx")
        node_info = self._create_wiki_node(title, source_name=source_name)
        node_token = node_info["node_token"]
        document_id = node_info["obj_token"]  # The underlying docx document ID

        # Step 2: Convert markdown to Feishu blocks
        blocks = markdown_to_feishu_blocks(markdown_content)
        table_count = sum(1 for b in blocks if b.get("block_type") == 31)
        print(f"    Converted markdown to {len(blocks)} Feishu blocks"
              f" ({table_count} table(s))")

        # Step 3: Insert blocks into the document. Tables are created through the
        # descendant API so that Feishu renders real table blocks instead of a
        # flattened text fallback.
        self._insert_blocks(document_id, parent_block_id=document_id, blocks=blocks)

        # Construct the wiki URL
        base = self.config["feishu"]["base_url"].replace("open.", "")
        # Typical URL: https://your-domain.feishu.cn/wiki/{node_token}
        wiki_url = f"{base}/wiki/{node_token}"
        return wiki_url

    def _resolve_parent_node_token(self, source_name: Optional[str] = None) -> str:
        """Pick the parent node token for a source, falling back to the default parent."""
        if source_name and source_name in self.source_parent_node_tokens:
            return self.source_parent_node_tokens[source_name]
        return self.parent_node_token

    def _create_wiki_node(self, title: str, source_name: Optional[str] = None) -> dict:
        """Create a new wiki node and return the node info."""
        body = {
            "obj_type": "docx",
            "node_type": "origin",
            "title": title,
        }
        parent_node_token = self._resolve_parent_node_token(source_name)
        if parent_node_token:
            body["parent_node_token"] = parent_node_token

        data = self.client.request(
            "POST",
            f"/open-apis/wiki/v2/spaces/{self.space_id}/nodes",
            json=body,
        )
        return data["data"]["node"]

    def _insert_blocks(self, document_id: str, parent_block_id: str, blocks: list):
        """Insert blocks as children. Feishu limits ~50 blocks per request."""
        buffer = []
        for block in blocks:
            if block.get("block_type") == 31:
                self._flush_block_buffer(document_id, parent_block_id, buffer)
                buffer = []
                self._insert_table_block(document_id, parent_block_id, block)
                continue
            if block.get("block_type") == 19:
                self._flush_block_buffer(document_id, parent_block_id, buffer)
                buffer = []
                self._insert_callout_block(document_id, parent_block_id, block)
                continue
            buffer.append(block)

        self._flush_block_buffer(document_id, parent_block_id, buffer)

    def _flush_block_buffer(self, document_id: str, parent_block_id: str, blocks: list):
        """Upload a list of already-normalized blocks in API-sized chunks."""
        if not blocks:
            return

        chunk_size = 50
        for i in range(0, len(blocks), chunk_size):
            chunk = [self._strip_internal_fields(block) for block in blocks[i : i + chunk_size]]
            self.client.request(
                "POST",
                f"/open-apis/docx/v1/documents/{document_id}/blocks/{parent_block_id}/children",
                json={"children": chunk, "index": -1},
            )

    def _insert_table_block(self, document_id: str, parent_block_id: str, table_block: dict):
        """Create a real Feishu table via the descendant API."""
        payload = self._build_table_descendant_payload(table_block)
        self.client.request(
            "POST",
            f"/open-apis/docx/v1/documents/{document_id}/blocks/{parent_block_id}/descendant",
            json=payload,
        )

    def _insert_callout_block(self, document_id: str, parent_block_id: str, callout_block: dict):
        """Create a callout block and its nested children via the descendant API."""
        payload = self._build_callout_descendant_payload(callout_block)
        self.client.request(
            "POST",
            f"/open-apis/docx/v1/documents/{document_id}/blocks/{parent_block_id}/descendant",
            json=payload,
        )

    def _build_table_descendant_payload(self, table_block: dict) -> dict:
        """Build a descendant API payload for one markdown table."""
        rows = table_block.get("_table_rows") or []
        if not rows:
            return {"children_id": [], "index": -1, "descendants": []}

        row_size = table_block["table"]["property"]["row_size"]
        column_size = table_block["table"]["property"]["column_size"]
        column_width = self._estimate_column_widths(rows, column_size)
        temp_ids = self._TempIdFactory()

        table_id = temp_ids.next("table")
        cell_ids = []
        descendants = [{
            "block_id": table_id,
            "block_type": 31,
            "table": {
                "property": {
                    "row_size": row_size,
                    "column_size": column_size,
                    "column_width": column_width,
                    "header_row": row_size > 0,
                }
            },
            "children": [],
        }]

        for row in rows:
            for cell in row:
                cell_id = temp_ids.next("cell")
                text_id = temp_ids.next("cell_text")
                cell_ids.append(cell_id)
                descendants.append({
                    "block_id": cell_id,
                    "block_type": 32,
                    "table_cell": {},
                    "children": [text_id],
                })
                descendants.append({
                    "block_id": text_id,
                    "block_type": 2,
                    "text": {
                        "elements": cell.get("elements") or [self._text_run("", {})],
                        "style": {},
                    },
                    "children": [],
                })

        descendants[0]["children"] = cell_ids
        return {
            "index": -1,
            "children_id": [table_id],
            "descendants": [self._strip_internal_fields(block) for block in descendants],
        }

    def _build_callout_descendant_payload(self, callout_block: dict) -> dict:
        """Build a descendant API payload for one callout with nested content."""
        children = callout_block.get("_children") or []
        temp_ids = self._TempIdFactory()
        callout_id = temp_ids.next("callout")
        callout_style = dict(callout_block.get("callout", {}))
        descendants = [{
            "block_id": callout_id,
            "block_type": 19,
            "callout": callout_style,
            "children": [],
        }]

        child_ids, child_descendants = self._build_descendants_from_blocks(children, temp_ids)
        descendants[0]["children"] = child_ids
        descendants.extend(child_descendants)
        return {
            "index": -1,
            "children_id": [callout_id],
            "descendants": [self._strip_internal_fields(block) for block in descendants],
        }

    def _build_descendants_from_blocks(self, blocks: list, temp_ids) -> tuple[list, list]:
        """Build descendant nodes for nested upload-capable blocks."""
        root_ids = []
        descendants = []
        for block in blocks:
            block_type = block.get("block_type")
            block_id = temp_ids.next(f"block_{block_type}")
            node = self._strip_internal_fields({**block, "block_id": block_id, "children": []})
            child_blocks = block.get("_children") or []
            descendants.append(node)
            if child_blocks:
                child_ids, child_descendants = self._build_descendants_from_blocks(child_blocks, temp_ids)
                node["children"] = child_ids
                descendants.extend(child_descendants)
            root_ids.append(block_id)
        return root_ids, descendants

    def _estimate_column_widths(self, rows: list, column_size: int) -> list[int]:
        """Estimate readable table column widths from cell content lengths."""
        widths = []
        for col_idx in range(column_size):
            max_len = max(
                len((row[col_idx].get("text", "") if col_idx < len(row) else "").strip())
                for row in rows
            )
            width = min(max(160, max_len * 18), 420)
            widths.append(width)
        return widths

    def _strip_internal_fields(self, value):
        """Remove internal helper fields before sending payloads to Feishu."""
        if isinstance(value, dict):
            return {
                key: self._strip_internal_fields(val)
                for key, val in value.items()
                if not key.startswith("_")
            }
        if isinstance(value, list):
            return [self._strip_internal_fields(item) for item in value]
        return value

    def _text_run(self, content: str, style: dict) -> dict:
        """Create a text_run element."""
        return {"text_run": {"content": content, "text_element_style": style}}

    class _TempIdFactory:
        """Generate stable temporary IDs for descendant API payloads."""

        def __init__(self):
            self._counter = 0

        def next(self, prefix: str) -> str:
            self._counter += 1
            return f"{prefix}_{self._counter}"
