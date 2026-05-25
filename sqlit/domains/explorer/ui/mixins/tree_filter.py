"""Tree filter mixin for SSMSTUI."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from rich.markup import escape as escape_markup

from sqlit.domains.explorer.ui.tree import expansion_state
from sqlit.domains.explorer.ui.tree import loaders as tree_loaders
from sqlit.shared.core.utils import fuzzy_match, highlight_matches
from sqlit.shared.ui.protocols import TreeFilterMixinHost

if TYPE_CHECKING:
    pass


@dataclass
class _NodeSnapshot:
    """Frozen capture of one tree node's state, used to restore the tree
    between filter keystrokes without calling refresh_tree.

    Calling refresh_tree drops lazy-loaded children (e.g. tables under a
    database in multi-DB browse mode) because the re-expand triggers an
    async reload that doesn't complete before the next filter pass — see
    issue #141.
    """

    label: Any
    data: Any
    allow_expand: bool
    is_expanded: bool
    children: list["_NodeSnapshot"] = field(default_factory=list)


def _snapshot_node(node: Any) -> _NodeSnapshot:
    return _NodeSnapshot(
        label=node.label,
        data=node.data,
        allow_expand=getattr(node, "allow_expand", False),
        is_expanded=getattr(node, "is_expanded", False),
        children=[_snapshot_node(c) for c in node.children],
    )


def _restore_node_under(parent: Any, snap: _NodeSnapshot) -> None:
    child = parent.add(snap.label, data=snap.data)
    try:
        child.allow_expand = snap.allow_expand
    except Exception:
        pass
    if snap.is_expanded:
        try:
            child.expand()
        except Exception:
            pass
    for grandchild in snap.children:
        _restore_node_under(child, grandchild)


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
    _tree_snapshot: list[_NodeSnapshot] | None = None

    def action_tree_filter(self: TreeFilterMixinHost) -> None:
        """Open the tree filter."""
        if not self.object_tree.has_focus:
            self.object_tree.focus()

        self._begin_tree_filter_session()
        self._update_tree_filter()
        self._update_footer_bindings()

    def _begin_tree_filter_session(self: TreeFilterMixinHost) -> None:
        """Reset transient filter state and show the filter input for a new session."""
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
        # Freeze the currently loaded tree (incl. lazy-loaded children)
        # so we can restore it between keystrokes without calling
        # refresh_tree, which would lose async-loaded folder contents.
        self._tree_snapshot = [
            _snapshot_node(c) for c in self.object_tree.root.children
        ]
        self.tree_filter_input.show()

    def action_tree_filter_close(self: TreeFilterMixinHost) -> None:
        """Close the tree filter and restore tree."""
        self._close_tree_filter_state()

    def _close_tree_filter_state(self: TreeFilterMixinHost) -> None:
        """Close filter UI, optionally rebuilding the tree to show all nodes."""
        self._tree_filter_visible = False
        self._tree_filter_text = ""
        self._tree_filter_query = ""
        self._tree_filter_fuzzy = False
        self._tree_filter_regex_mode = False
        self._tree_filter_regex = None
        self._tree_filter_regex_error = None
        self._tree_filter_typing = False
        self.tree_filter_input.hide()
        self._restore_tree_labels()
        self._restore_tree_from_snapshot()
        self._tree_snapshot = None
        self._update_footer_bindings()

    def action_tree_filter_accept(self: TreeFilterMixinHost) -> None:
        """Accept current filter selection, close filter, and activate the node."""
        current_node = None
        # Remember the match's *data* (not the node reference) before closing.
        # Closing the filter rebuilds the tree from the snapshot taken at
        # filter-open time, which replaces every node object — so the
        # reference we captured here would be stale after close. The data
        # payload, however, is the same object on both old and new nodes
        # (we pass it through unchanged in _restore_node_under), so we can
        # re-locate the match by identity.
        matched_data: Any = None
        if (
            self._tree_filter_matches
            and self._tree_filter_match_index < len(self._tree_filter_matches)
        ):
            current_node = self._tree_filter_matches[self._tree_filter_match_index]
            if current_node and current_node.data:
                matched_data = current_node.data
        self.action_tree_filter_close()

        if matched_data is None:
            return

        fresh_node = self._find_node_by_data(matched_data)
        if fresh_node is None:
            return

        # Textual's Tree.move_cursor reads `node._line`, which is set during
        # the next layout pass — not when the node is `add()`-ed. Since the
        # snapshot restore that just ran in action_tree_filter_close added
        # all fresh nodes synchronously, calling move_cursor right now sees
        # stale `_line` values and parks the cursor on the wrong row.
        # Defer the move (and the activation) until after the next refresh.
        call_after = getattr(self, "call_after_refresh", None)
        if callable(call_after):
            call_after(lambda: self._select_and_activate_after_refresh(fresh_node))
        else:
            # Synchronous fallback (used in unit tests with a mock host).
            self._select_and_activate_after_refresh(fresh_node)

    def _select_and_activate_after_refresh(self: TreeFilterMixinHost, node: Any) -> None:
        try:
            self.object_tree.move_cursor(node)
        except Exception:
            pass
        self._activate_tree_node(node)

    def _find_node_by_data(self: TreeFilterMixinHost, data: Any) -> Any | None:
        """Locate the node in the current tree whose `.data` is `data`."""
        stack = [self.object_tree.root]
        while stack:
            node = stack.pop()
            if node.data is data:
                return node
            stack.extend(node.children)
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
        if getattr(self, "_tree_filter_scope_path", None):
            self._move_tree_cursor_to_node(node)
            return
        # Expand ancestors to make node visible
        self._expand_ancestors(node)
        # Move cursor to node
        self.object_tree.move_cursor(node)

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
        search_root = self.object_tree.root
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

        # Restore from the snapshot taken when the filter opened, so each
        # filter pass searches every node (not just the survivors of the
        # previous narrower filter — see PR #211 for the backspace case)
        # while preserving lazy-loaded children that refresh_tree would
        # have dropped (issue #141).
        self._restore_tree_from_snapshot()
        self._tree_original_labels = {}

        total = self._count_all_nodes()

        if not self._tree_filter_query:
            if self._tree_filter_applied or self._tree_filter_matches or self._tree_original_labels:
                self._show_all_tree_nodes()
            self._tree_filter_matches = []
            self._tree_filter_applied = False
            self.tree_filter_input.set_filter("", 0, total)
            return

        if search_root is None:
            self._tree_filter_matches = []
            self._tree_filter_match_index = 0
            self.tree_filter_input.set_filter(self._tree_filter_text, 0, 0)
            return

        # Find all matching nodes. The default Explorer filter keeps main's
        # connection/database-only behavior; Table Filter searches inside its scoped subtree.
        matches: list[Any] = []
        self._find_matching_nodes(search_root, matches)

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

    def _find_matching_nodes(self: TreeFilterMixinHost, node: Any, matches: list) -> bool:
        """Recursively find nodes matching the filter.

        Returns True if this node or any descendant matches.
        """
        node_matches = False
        has_matching_child = False

        # Check children first. The default Explorer filter only searches the
        # connection/database hierarchy; scoped Table Filter descends into the
        # Tables subtree.
        for child in node.children:
            if self._find_matching_nodes(child, matches):
                has_matching_child = True

        # Get node label text for matching
        label_text = self._get_node_label_text(node)
        if label_text and self._get_node_kind(node) in ["connection_folder", "connection", "database"]:
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

        return node_matches or has_matching_child

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
        pending_ids: set[int] = set()

        # Collect all ancestor IDs
        for node in self._tree_filter_matches:
            current = node.parent
            while current and current != self.object_tree.root:
                ancestor_ids.add(id(current))
                current = current.parent

        # Hide non-matching, non-ancestor nodes
        self._set_node_visibility(self.object_tree.root, match_ids, ancestor_ids, pending_ids)

    def _set_node_visibility(
        self: TreeFilterMixinHost,
        node: Any,
        match_ids: set,
        ancestor_ids: set,
        pending_ids: set,
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
                self._set_node_visibility(child, match_ids, ancestor_ids, pending_ids)

        # Remove non-matching nodes
        for child in nodes_to_remove:
            try:
                child.remove()
            except Exception:
                pass

    def _show_all_tree_nodes(self: TreeFilterMixinHost) -> None:
        """Rebuild the tree to restore all nodes after filtering."""
        if self._tree_snapshot is not None:
            self._restore_tree_from_snapshot()
        else:
            # Fallback for paths that aren't inside an open filter session.
            self.refresh_tree()

    def _restore_tree_from_snapshot(self: TreeFilterMixinHost) -> None:
        """Rebuild the root's children from the snapshot taken at filter open."""
        snapshot = self._tree_snapshot
        if snapshot is None:
            return
        root = self.object_tree.root
        # Clear existing children (works for both Textual TreeNode and the
        # test mock — both implement child.remove()).
        for child in list(root.children):
            try:
                child.remove()
            except Exception:
                pass
        for snap in snapshot:
            _restore_node_under(root, snap)

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
            if node.data and self._get_node_label_text(node) and self._tree_filter_can_match_node(node):
                count += 1
            for child in node.children:
                count_nodes(child)

        start = root or self.object_tree.root
        if root is None:
            count_nodes(start)
        else:
            for child in getattr(start, "children", []):
                count_nodes(child)
        return count
