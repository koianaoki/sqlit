"""Tree filter mixin for SSMSTUI."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape as escape_markup

from sqlit.domains.explorer.ui.tree import expansion_state
from sqlit.domains.explorer.ui.tree import loaders as tree_loaders
from sqlit.shared.core.utils import fuzzy_match, highlight_matches
from sqlit.shared.ui.protocols import TreeFilterMixinHost

if TYPE_CHECKING:
    pass


class TreeFilterMixin:
    """Mixin providing tree filter functionality."""

    _tree_filter_visible: bool = False
    _tree_filter_text: str = ""
    _tree_filter_query: str = ""
    _tree_filter_fuzzy: bool = False
    _tree_filter_regex_mode: bool = False
    _tree_filter_regex: re.Pattern[str] | None = None
    _tree_filter_regex_error: str | None = None
    _tree_filter_typing: bool = False
    _tree_filter_matches: list[Any] = []
    _tree_filter_match_index: int = 0
    _tree_original_labels: dict[int, str] = {}
    _tree_filter_applied: bool = False
    _tree_filter_scope_path: str | None = None

    _TREE_FILTER_LOADABLE_FOLDERS = {
        "databases",
        "tables",
        "views",
        "indexes",
        "triggers",
        "sequences",
        "procedures",
    }

    def action_tree_filter(self: TreeFilterMixinHost) -> None:
        """Open the tree filter."""
        if not self.object_tree.has_focus:
            self.object_tree.focus()

        self._tree_filter_visible = True
        self._tree_filter_text = ""
        self._tree_filter_query = ""
        self._tree_filter_fuzzy = False
        self._tree_filter_regex_mode = False
        self._tree_filter_regex = None
        self._tree_filter_regex_error = None
        self._tree_filter_typing = True
        self._tree_filter_matches = []
        self._tree_filter_match_index = 0
        self._tree_original_labels = {}
        self._tree_filter_applied = False
        self._tree_filter_scope_path = None

        self.tree_filter_input.show()
        self._ensure_tree_filter_search_nodes_loaded()
        self._update_tree_filter()
        self._update_footer_bindings()

    def action_table_filter(self: TreeFilterMixinHost) -> None:
        """Open a table-only filter for the selected database node."""
        if not self.object_tree.has_focus:
            self.object_tree.focus()

        tables_node = self._get_table_filter_tables_folder()
        if tables_node is None:
            notify = getattr(self, "notify", None)
            if callable(notify):
                notify("Tables folder is not available for this database", severity="warning")
            return

        try:
            tables_node.expand()
        except Exception:
            pass

        self._tree_filter_visible = True
        self._tree_filter_text = ""
        self._tree_filter_query = ""
        self._tree_filter_fuzzy = False
        self._tree_filter_regex_mode = False
        self._tree_filter_regex = None
        self._tree_filter_regex_error = None
        self._tree_filter_typing = True
        self._tree_filter_matches = []
        self._tree_filter_match_index = 0
        self._tree_original_labels = {}
        self._tree_filter_applied = False
        self._tree_filter_scope_path = expansion_state.get_node_path(cast(Any, self), tables_node) or None
        self._remember_tree_filter_path(self._tree_filter_scope_path, include_self=True)

        self.tree_filter_input.show()
        self._ensure_tree_filter_search_nodes_loaded()
        self._update_tree_filter()
        self._update_footer_bindings()

    def action_tree_filter_close(self: TreeFilterMixinHost) -> None:
        """Close the tree filter and restore tree."""
        self._tree_filter_visible = False
        self._tree_filter_text = ""
        self._tree_filter_query = ""
        self._tree_filter_fuzzy = False
        self._tree_filter_regex_mode = False
        self._tree_filter_regex = None
        self._tree_filter_regex_error = None
        self._tree_filter_typing = False
        self._tree_filter_scope_path = None
        self.tree_filter_input.hide()
        self._restore_tree_labels()
        self._show_all_tree_nodes()
        self._tree_filter_applied = False
        self._update_footer_bindings()

    def action_tree_filter_accept(self: TreeFilterMixinHost) -> None:
        """Accept current filter selection, close filter, and activate the node."""
        # Store current match before closing. The tree is rebuilt on close,
        # so keep a stable path and restore the cursor to the rebuilt node.
        current_node = None
        current_path = ""
        if self._tree_filter_matches and self._tree_filter_match_index < len(self._tree_filter_matches):
            current_node = self._tree_filter_matches[self._tree_filter_match_index]
            current_path = expansion_state.get_node_path(cast(Any, self), current_node)
            self._remember_tree_filter_path(current_path)
            self._move_tree_cursor_to_node(current_node)

        # Close the filter
        self.action_tree_filter_close()

        if current_path:
            restored_node = self._restore_tree_filter_cursor_path(current_path)
            if restored_node is not None:
                current_node = restored_node

        # Activate the selected node (connect to server, expand folder, etc.)
        if current_node and current_node.data:
            self._activate_tree_node(current_node)

    def _move_tree_cursor_to_node(self: TreeFilterMixinHost, node: Any) -> None:
        """Move the Explorer cursor to a node, falling back for test doubles."""
        self._expand_ancestors(node)
        move_cursor = getattr(self.object_tree, "move_cursor", None)
        if callable(move_cursor):
            move_cursor(node)
        else:
            self.object_tree.select_node(node)
        update_footer = getattr(self, "_update_footer_bindings", None)
        if callable(update_footer):
            update_footer()

    def _restore_tree_filter_cursor_path(self: TreeFilterMixinHost, path: str, attempt: int = 0) -> Any | None:
        """Restore cursor to a filtered match after the tree is rebuilt/reloaded."""
        self._remember_tree_filter_path(path)
        restored_node = expansion_state.find_node_by_path(cast(Any, self), self.object_tree.root, path)
        if restored_node is not None:
            self._move_tree_cursor_to_node(restored_node)
            return restored_node

        if attempt >= 8:
            return None

        def retry() -> None:
            self._restore_tree_filter_cursor_path(path, attempt + 1)

        call_after_refresh = getattr(self, "call_after_refresh", None)
        if callable(call_after_refresh):
            call_after_refresh(retry)
            return None

        set_timer = getattr(self, "set_timer", None)
        if callable(set_timer):
            set_timer(0.05, retry)
            return None

        call_later = getattr(self, "call_later", None)
        if callable(call_later):
            call_later(retry)
            return None

        return None

    def action_tree_filter_next(self: TreeFilterMixinHost) -> None:
        """Move to next filter match."""
        if not self._tree_filter_matches:
            return
        self._tree_filter_match_index = (self._tree_filter_match_index + 1) % len(
            self._tree_filter_matches
        )
        self._jump_to_current_match()

    def action_tree_filter_prev(self: TreeFilterMixinHost) -> None:
        """Move to previous filter match."""
        if not self._tree_filter_matches:
            return
        self._tree_filter_match_index = (self._tree_filter_match_index - 1) % len(
            self._tree_filter_matches
        )
        self._jump_to_current_match()

    def _jump_to_current_match(self: TreeFilterMixinHost) -> None:
        """Jump to the current match in the tree."""
        if not self._tree_filter_matches:
            return
        node = self._tree_filter_matches[self._tree_filter_match_index]
        # Expand ancestors to make node visible
        self._expand_ancestors(node)
        # Select the node
        self.object_tree.select_node(node)

    def _expand_ancestors(self: TreeFilterMixinHost, node: Any) -> None:
        """Expand all ancestor nodes to make a node visible."""
        ancestors = []
        current = node.parent
        while current and current != self.object_tree.root:
            ancestors.append(current)
            current = current.parent
        # Expand from root down
        for ancestor in reversed(ancestors):
            ancestor.expand()

    def on_key(self: TreeFilterMixinHost, event: Any) -> None:
        """Handle key events when tree filter is active."""
        if not self._tree_filter_visible:
            # Pass to next mixin in chain (e.g., AutocompleteMixin)
            super().on_key(event)  # type: ignore[misc]
            return

        key = event.key
        if key == "enter":
            self.action_tree_filter_accept()
            event.prevent_default()
            event.stop()
            return

        if not self._tree_filter_typing:
            if key in ("n", "j"):
                self.action_tree_filter_next()
                event.prevent_default()
                event.stop()
                return

            if key in ("N", "k"):
                self.action_tree_filter_prev()
                event.prevent_default()
                event.stop()
                return

            if key == "/":
                self.action_tree_filter()
                event.prevent_default()
                event.stop()
                return

        # Handle backspace
        if key == "backspace":
            if self._tree_filter_typing:
                if self._tree_filter_text:
                    self._tree_filter_text = self._tree_filter_text[:-1]
                    self._update_tree_filter()
                else:
                    # Exit filter when backspacing with no text
                    self.action_tree_filter_close()
            event.prevent_default()
            event.stop()
            return

        # Handle printable characters - use event.character for proper shift support
        # event.key might be "shift+?" but event.character will be "?"
        char = getattr(event, "character", None)
        if char and char.isprintable():
            if char == "/" and not self._tree_filter_typing:
                self.action_tree_filter()
                event.prevent_default()
                event.stop()
                return
            if not self._tree_filter_typing:
                super().on_key(event)  # type: ignore[misc]
                return
            self._tree_filter_text += char
            self._update_tree_filter()
            event.prevent_default()
            event.stop()
            return

        # Pass unhandled keys to next mixin
        super().on_key(event)  # type: ignore[misc]

    def _update_tree_filter(self: TreeFilterMixinHost) -> None:
        """Update the tree based on current filter text."""
        self._restore_tree_labels()
        search_root = self._get_tree_filter_search_root()
        total = self._count_all_nodes(search_root)
        raw_text = self._tree_filter_text
        self._tree_filter_fuzzy = raw_text.startswith("~")
        self._tree_filter_regex_mode = False
        self._tree_filter_regex = None
        self._tree_filter_regex_error = None

        if self._tree_filter_fuzzy:
            self._tree_filter_query = raw_text[1:]
        else:
            regex_query = self._extract_tree_filter_regex_query(raw_text)
            if regex_query is None:
                self._tree_filter_query = raw_text
            else:
                self._tree_filter_regex_mode = True
                self._tree_filter_query = regex_query
                if regex_query:
                    try:
                        self._tree_filter_regex = re.compile(regex_query, re.IGNORECASE)
                    except re.error as error:
                        self._tree_filter_regex_error = str(error)

        if not self._tree_filter_query:
            if self._tree_filter_applied or self._tree_filter_matches or self._tree_original_labels:
                self._show_all_tree_nodes()
            self._tree_filter_matches = []
            self._tree_filter_applied = False
            self._ensure_tree_filter_search_nodes_loaded()
            self.tree_filter_input.set_filter("", 0, total)
            return

        self._ensure_tree_filter_search_nodes_loaded()

        # Find all matching nodes inside the current filter scope.
        matches: list[Any] = []
        self._find_matching_nodes(search_root, matches, include_self=False)

        self._tree_filter_matches = matches
        self._tree_filter_match_index = 0

        # Hide non-matching nodes and highlight matches
        self._apply_filter_to_tree()
        self._tree_filter_applied = True

        # Update filter display
        self.tree_filter_input.set_filter(
            self._tree_filter_text, len(matches), total
        )

        # Jump to first match
        if matches:
            self._jump_to_current_match()

    def _get_table_filter_tables_folder(self: TreeFilterMixinHost) -> Any | None:
        """Return the Tables folder for the selected database, Tables folder, or table."""
        node = getattr(self.object_tree, "cursor_node", None)
        if node is None:
            return None

        if self._get_node_kind(node) == "database":
            for child in getattr(node, "children", []):
                data = getattr(child, "data", None)
                if self._get_node_kind(child) == "folder" and getattr(data, "folder_type", "") == "tables":
                    return child
            return None

        current = node
        while current and current != self.object_tree.root:
            data = getattr(current, "data", None)
            if self._get_node_kind(current) == "folder" and getattr(data, "folder_type", "") == "tables":
                return current
            current = getattr(current, "parent", None)
        return None

    def _remember_tree_filter_path(self: TreeFilterMixinHost, path: str | None, *, include_self: bool = False) -> None:
        """Keep ancestors expanded and cursor restoration pending across filter rebuilds."""
        if not path:
            return
        parts = [part for part in path.split("/") if part]
        end = len(parts) + 1 if include_self else len(parts)
        expanded_paths: Any = getattr(self, "_expanded_paths", set())
        if isinstance(expanded_paths, set):
            for index in range(1, end):
                expanded_paths.add("/".join(parts[:index]))
            self._expanded_paths = expanded_paths
        if not include_self:
            cast(Any, self)._pending_tree_cursor_path = path
            cast(Any, self)._pending_tree_cursor_connection = ""

    def _get_tree_filter_search_root(self: TreeFilterMixinHost) -> Any:
        """Return the subtree that should be searched by the active explorer filter."""
        path = getattr(self, "_tree_filter_scope_path", None)
        if path:
            scoped_node = expansion_state.find_node_by_path(cast(Any, self), self.object_tree.root, path)
            if scoped_node is not None:
                return scoped_node
        return self.object_tree.root

    def _extract_tree_filter_regex_query(self: TreeFilterMixinHost, raw_text: str) -> str | None:
        """Return regex pattern when the filter text uses a regex prefix."""
        if raw_text.startswith("re:"):
            return raw_text[3:]
        if raw_text.startswith("r:"):
            return raw_text[2:]
        if raw_text.startswith("/"):
            return raw_text[1:]
        return None

    def _match_tree_filter_regex(self: TreeFilterMixinHost, label_text: str) -> tuple[bool, list[int]]:
        """Match label text with the compiled tree-filter regex and return highlight indices."""
        regex = self._tree_filter_regex
        if regex is None:
            return False, []

        indices: set[int] = set()
        matched = False
        for match in regex.finditer(label_text):
            matched = True
            start, end = match.span()
            if start == end:
                continue
            indices.update(range(start, end))
        return matched, sorted(indices)

    def _find_matching_nodes(
        self: TreeFilterMixinHost, node: Any, matches: list, include_self: bool = True
    ) -> bool:
        """Recursively find nodes matching the filter.

        Returns True if this node or any descendant matches.
        """
        node_matches = False
        has_matching_child = False

        # Check children first
        for child in node.children:
            if self._find_matching_nodes(child, matches):
                has_matching_child = True

        # Get node label text for matching
        label_text = self._get_node_label_text(node)
        if include_self and label_text:
            if self._tree_filter_fuzzy:
                matched, indices = fuzzy_match(self._tree_filter_query, label_text)
            elif self._tree_filter_regex_mode:
                matched, indices = self._match_tree_filter_regex(label_text)
            else:
                label_lower = label_text.lower()
                query_lower = self._tree_filter_query.lower()
                start = label_lower.find(query_lower)
                matched = start >= 0
                indices = list(range(start, start + len(self._tree_filter_query))) if matched else []

            if matched:
                node_matches = True
                matches.append(node)
                # Store original label and apply highlighting
                self._tree_original_labels[id(node)] = str(node.label)
                highlighted = highlight_matches(
                    escape_markup(label_text), indices, style="bold #FFFF00"
                )
                # Preserve any existing markup prefix (like icons, colors)
                node.set_label(self._rebuild_label_with_highlight(node, highlighted))

        return node_matches or has_matching_child or self._tree_filter_node_has_pending_load(node)

    def _ensure_tree_filter_search_nodes_loaded(self: TreeFilterMixinHost) -> bool:
        """Start loading unloaded explorer folders so filters can match their objects."""
        if getattr(self, "current_connection", None) is None or getattr(self, "current_provider", None) is None:
            return False

        started = False
        stack = [self._get_tree_filter_search_root()]
        while stack:
            node = stack.pop()
            if self._tree_filter_should_load_node(node):
                started = self._start_tree_filter_node_load(node) or started
            stack.extend(reversed(getattr(node, "children", [])))
        return started

    def _tree_filter_should_load_node(self: TreeFilterMixinHost, node: Any) -> bool:
        """Return True when a node may contain searchable children that are not loaded yet."""
        data = getattr(node, "data", None)
        if data is None:
            return False
        if self._get_node_kind(node) != "folder":
            return False
        folder_type = getattr(data, "folder_type", "")
        if folder_type not in self._TREE_FILTER_LOADABLE_FOLDERS:
            return False
        children = list(getattr(node, "children", []))
        return not children or (len(children) == 1 and self._get_node_kind(children[0]) == "loading")

    def _start_tree_filter_node_load(self: TreeFilterMixinHost, node: Any) -> bool:
        """Expand and load a folder node for explorer filtering."""
        children = list(getattr(node, "children", []))
        if children and not (len(children) == 1 and self._get_node_kind(children[0]) == "loading"):
            return False

        try:
            node.expand()
        except Exception:
            pass

        if children:
            return False

        node_path = expansion_state.get_node_path(cast(Any, self), node)
        if not node_path:
            return False
        loading_nodes = tree_loaders.ensure_loading_nodes(cast(Any, self))
        if node_path in loading_nodes:
            return False

        loading_nodes.add(node_path)
        tree_loaders.add_loading_placeholder(cast(Any, self), node)
        self._load_folder_async(node, node.data)
        return True

    def _tree_filter_node_has_pending_load(self: TreeFilterMixinHost, node: Any) -> bool:
        """Keep loading folders visible until their children can be filtered."""
        if not self._tree_filter_query or self._get_node_kind(node) != "folder":
            return False
        children = list(getattr(node, "children", []))
        return len(children) == 1 and self._get_node_kind(children[0]) == "loading"

    def _get_node_label_text(self, node: Any) -> str:
        """Get the plain text label for a node."""
        data = node.data
        if data is None:
            return ""
        label_getter = getattr(data, "get_label_text", None)
        if callable(label_getter):
            value = label_getter()
            if isinstance(value, str):
                return value
            return "" if value is None else str(value)
        return ""

    def _rebuild_label_with_highlight(self, node: Any, highlighted_text: str) -> str:
        """Rebuild the node label with highlighted text."""
        data = node.data
        if data is None:
            return highlighted_text
        return highlighted_text

    def _apply_filter_to_tree(self: TreeFilterMixinHost) -> None:
        """Hide nodes that don't match and aren't ancestors of matches."""
        match_ids = {id(n) for n in self._tree_filter_matches}
        ancestor_ids = set()
        pending_ids = set()
        scope_node = self._get_tree_filter_search_root()

        def collect_pending(node: Any) -> None:
            if self._tree_filter_node_has_pending_load(node):
                pending_ids.add(id(node))
                for child in getattr(node, "children", []):
                    pending_ids.add(id(child))
            for child in getattr(node, "children", []):
                collect_pending(child)

        collect_pending(scope_node)

        # Keep the scoped subtree reachable from the root while filtering.
        current = scope_node
        while current and current != self.object_tree.root:
            ancestor_ids.add(id(current))
            current = current.parent

        # Collect all ancestor IDs
        for node in self._tree_filter_matches:
            current = node.parent
            while current and current != self.object_tree.root:
                ancestor_ids.add(id(current))
                current = current.parent

        # Hide non-matching, non-ancestor nodes
        self._set_node_visibility(
            self.object_tree.root, match_ids, ancestor_ids, pending_ids, visible=True
        )

    def _set_node_visibility(
        self: TreeFilterMixinHost,
        node: Any,
        match_ids: set,
        ancestor_ids: set,
        pending_ids: set,
        visible: bool,
    ) -> None:
        """Recursively set node visibility by removing non-matching nodes."""
        # Collect nodes to remove (can't modify children while iterating)
        nodes_to_remove: list[Any] = []

        for child in node.children:
            child_id = id(child)
            is_match = child_id in match_ids
            is_ancestor = child_id in ancestor_ids
            is_pending = child_id in pending_ids
            should_show = is_match or is_ancestor or is_pending or not self._tree_filter_query

            if not should_show and self._tree_filter_query:
                # Mark for removal
                nodes_to_remove.append(child)
            else:
                # Recurse into visible nodes
                self._set_node_visibility(child, match_ids, ancestor_ids, pending_ids, should_show)

        # Remove non-matching nodes
        for child in nodes_to_remove:
            try:
                child.remove()
            except Exception:
                pass

    def _show_all_tree_nodes(self: TreeFilterMixinHost) -> None:
        """Rebuild the tree to restore all nodes after filtering."""
        self.refresh_tree()

    def _restore_tree_labels(self: TreeFilterMixinHost) -> None:
        """Restore original labels for all modified nodes."""
        def restore_node(node: Any) -> None:
            node_id = id(node)
            if node_id in self._tree_original_labels:
                node.set_label(self._tree_original_labels[node_id])
            for child in node.children:
                restore_node(child)

        restore_node(self.object_tree.root)
        self._tree_original_labels = {}

    def _count_all_nodes(self: TreeFilterMixinHost, root: Any | None = None) -> int:
        """Count all searchable nodes in the current filter scope."""
        count = 0

        def count_nodes(node: Any) -> None:
            nonlocal count
            if node.data and self._get_node_label_text(node):
                count += 1
            for child in node.children:
                count_nodes(child)

        start = root or self.object_tree.root
        for child in getattr(start, "children", []):
            count_nodes(child)
        return count
