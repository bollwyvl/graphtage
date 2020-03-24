import heapq
import itertools

from abc import abstractmethod, ABCMeta
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union


def levenshtein_distance(s: str, t: str) -> int:
    rows = len(s) + 1
    cols = len(t) + 1
    dist: List[List[int]] = [[0] * cols for _ in range(rows)]

    for i in range(1, rows):
        dist[i][0] = i

    for i in range(1, cols):
        dist[0][i] = i

    for col in range(1, cols):
        for row in range(1, rows):
            if s[row - 1] == t[col - 1]:
                cost = 0
            else:
                cost = 1
            dist[row][col] = min(dist[row - 1][col] + 1,
                                 dist[row][col - 1] + 1,
                                 dist[row - 1][col - 1] + cost)

    return dist[row][col]


class Range:
    def __init__(self, lower_bound: int = None, upper_bound: int = None):
        assert (lower_bound is None or lower_bound >= 0) and \
               (upper_bound is None or upper_bound >= 0) and \
               (lower_bound is None or upper_bound is None or upper_bound >= lower_bound)
        self.lower_bound: int = lower_bound
        self.upper_bound: int = upper_bound

    def __lt__(self, other):
        return self.upper_bound is not None and other.lower_bound is not None and self.upper_bound < other.lower_bound

    def __bool__(self):
        return self.lower_bound is not None and self.upper_bound is not None

    def __add__(self, other):
        if isinstance(other, int):
            return Range(self.lower_bound + other, self.upper_bound + other)
        else:
            return Range(self.lower_bound + other.lower_bound, self.upper_bound + other.upper_bound)

    def __radd__(self, other):
        return self + other

    def __sub__(self, other):
        if isinstance(other, int):
            return Range(self.lower_bound - other, self.upper_bound - other)
        else:
            return Range(self.lower_bound - other.lower_bound, self.upper_bound - other.upper_bound)

    def definitive(self) -> bool:
        return bool(self) and self.lower_bound == self.upper_bound

    def intersect(self, other):
        if not self or not other or self < other or other < self:
            return Range()
        elif self.lower_bound < other.lower_bound:
            if self.upper_bound < other.upper_bound:
                return Range(other.lower_bound, self.upper_bound)
            else:
                return other
        elif self.upper_bound < other.upper_bound:
            return self
        else:
            return Range(self.lower_bound, other.upper_bound)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.lower_bound!r}, {self.upper_bound!r})"

    def __str__(self):
        return f"[{self.lower_bound}, {self.upper_bound}]"


class Edit(metaclass=ABCMeta):
    def __init__(self,
                 from_node,
                 to_node = None,
                 constant_cost: Optional[int] = 0,
                 cost_upper_bound: Optional[int] = None):
        self.from_node: TreeNode = from_node
        self.to_node: TreeNode = to_node
        self._constant_cost = constant_cost
        self._cost_upper_bound = cost_upper_bound
        self.initial_cost = self.cost()

    def tighten_bounds(self) -> bool:
        return False

    def __lt__(self, other):
        while True:
            if self.cost() < other.cost():
                return True
            elif self.cost().definitive() and other.cost().definitive():
                return False
            if not self.tighten_bounds() and not other.tighten_bounds():
                return False

    def __eq__(self, other):
        while True:
            if self.cost().definitive() and other.cost().definitive():
                return self.cost().lower_bound == other.cost().lower_bound
            self.tighten_bounds()
            other.tighten_bounds()

    def cost(self) -> Range:
        lb = self._constant_cost
        if self._cost_upper_bound is None:
            if self.to_node is None:
                ub = 0
            else:
                ub = self.from_node.total_size + self.to_node.total_size + 1
        else:
            ub = self._cost_upper_bound
        return Range(lb, ub)


class TreeNode(metaclass=ABCMeta):
    _total_size = None

    @abstractmethod
    def edits(self, node) -> Edit:
        return None

    @property
    def total_size(self) -> int:
        if self._total_size is None:
            self._total_size = self.calculate_total_size()
        return self._total_size

    @abstractmethod
    def calculate_total_size(self) -> int:
        return 0


class PossibleEdits(Edit):
    def __init__(self, from_node: TreeNode, to_node: TreeNode, edits: Iterator[Edit] = ()):
        self._unprocessed: Iterator[Edit] = edits
        self._untightened: List[Edit] = []
        self._tightened: List[Edit] = []
        super().__init__(from_node=from_node, to_node=to_node)

    @property
    def possibilities(self) -> Iterable[Edit]:
        return itertools.chain(iter(self._untightened), iter(self._tightened))

    @property
    def best_possibility(self) -> Edit:
        best: Edit = None
        for e in self.possibilities:
            if best is None or e.cost().upper_bound < best.cost().upper_bound:
                best = e
        return best

    def tighten_bounds(self) -> bool:
        if self._unprocessed is not None:
            try:
                next_best = next(self._unprocessed)
                if self._untightened and self._untightened[0] < next_best:
                    # No need to add this new edit if it is strictly worse than the current best!
                    pass
                else:
                    heapq.heappush(self._untightened, next_best)
                return True
            except StopIteration:
                self._unprocessed = None
                pass
        if self._untightened:
            next_best = heapq.heappop(self._untightened)
            if next_best.tighten_bounds():
                heapq.heappush(self._untightened, next_best)
            else:
                self._tightened.append(next_best)
            return True
        else:
            return False

    def cost(self) -> Range:
        if self._unprocessed is not None:
            return Range(0, max(self.from_node.total_size, self.to_node.total_size) + 1)
        lb = None
        ub = 0
        for e in self.possibilities:
            cost = e.cost()
            if lb is None:
                lb = cost.lower_bound
            else:
                lb = min(lb, cost.lower_bound)
            ub = max(ub, cost.upper_bound)
        return Range(lb, ub)


class ContainerNode(TreeNode, metaclass=ABCMeta):
    pass


class LeafNode(TreeNode):
    def __init__(self, object):
        self.object = object

    def calculate_total_size(self):
        return len(str(self.object))

    def edits(self, node: TreeNode) -> Edit:
        if isinstance(node, LeafNode):
            return Match(self, node, levenshtein_distance(str(self.object), str(node.object)))
        elif isinstance(node, ContainerNode):
            return Replace(self, node)

    def __lt__(self, other):
        if isinstance(other, LeafNode):
            return self.object < other.object
        else:
            return self.object < other

    def __eq__(self, other):
        if isinstance(other, LeafNode):
            return self.object == other.object
        else:
            return self.object == other

    def __hash__(self):
        return hash(self.object)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.object!r})"

    def __str__(self):
        return str(self.object)


class KeyValuePairNode(ContainerNode):
    def __init__(self, key: LeafNode, value: TreeNode):
        self.key: LeafNode = key
        self.value: TreeNode = value

    def edits(self, node: TreeNode) -> Edit:
        if not isinstance(node, KeyValuePairNode):
            raise RuntimeError("KeyValuePairNode.edits() should only ever be called with another KeyValuePair object!")
        return CompoundEdit(
            from_node=self,
            to_node=node,
            edits=iter((Match(self, node, 0), self.key.edits(node.key), self.value.edits(node.value)))
        )

    def calculate_total_size(self):
        return self.key.total_size + self.value.total_size

    def __lt__(self, other):
        return (self.key < other.key) or (self.key == other.key and self.value < other.value)

    def __eq__(self, other):
        return self.key == other.key and self.value == other.value

    def __hash__(self):
        return hash((self.key, self.value))

    def __len__(self):
        return 2

    def __iter__(self):
        yield self.key
        yield self.value

    def __repr__(self):
        return f"{self.__class__.__name__}(key={self.key!r}, value={self.value!r})"

    def __str__(self):
        return f"{self.key!s}: {self.value!s}"


class CompoundEdit(Edit):
    def __init__(self, from_node: TreeNode, to_node: Optional[TreeNode], edits: Iterator[Edit]):
        self._edit_iter = edits
        self._sub_edits = []
        cost_upper_bound = from_node.total_size + 1
        if to_node is not None:
            cost_upper_bound += to_node.total_size
        self._cost = None
        super().__init__(from_node=from_node,
                         to_node=to_node,
                         cost_upper_bound=cost_upper_bound)

    @property
    def sub_edits(self):
        while self._edit_iter is not None and self.tighten_bounds():
            pass
        return self._sub_edits

    def tighten_bounds(self) -> bool:
        if self._edit_iter is not None:
            try:
                next_edit = next(self._edit_iter)
                if isinstance(next_edit, CompoundEdit):
                    self._sub_edits.extend(next_edit.sub_edits)
                else:
                    self._sub_edits.append(next_edit)
                self._cost = None
                return True
            except StopIteration:
                self._edit_iter = None
        for child in self._sub_edits:
            if child.tighten_bounds():
                self._cost = None
                return True
        return False

    def cost(self) -> Range:
        if self._cost is None:
            if self._edit_iter is None:
                # We've expanded all of the sub-edits, so calculate the bounds explicitly:
                self._cost = sum(e.cost() for e in self._sub_edits)
            else:
                # We have not yet expanded all of the sub-edits
                bounds = super().cost()
                for e in self._sub_edits:
                    bounds = bounds + e.cost() - e.initial_cost
                self._cost = bounds
        return self._cost

    def __len__(self):
        return len(self.sub_edits)

    def __iter__(self) -> Iterator[Edit]:
        return iter(self.sub_edits)

    def __repr__(self):
        return f"{self.__class__.__name__}(*{self.sub_edits!r})"


class ListNode(ContainerNode):
    def __init__(self, list_like: Sequence[TreeNode]):
        self.children: Tuple[TreeNode] = tuple(list_like)

    def edits(self, node: TreeNode) -> Edit:
        if isinstance(node, ListNode):
            return PossibleEdits(self, node, self._match(node, self.children, node.children))
        else:
            return Replace(self, node)

    def _match(self, node: TreeNode, l1: Tuple[TreeNode], l2: Tuple[TreeNode]) -> Iterator[Edit]:
        if not l1 and not l2:
            return
        elif l1 and not l2:
            yield CompoundEdit(from_node=self, to_node=None, edits=(Remove(n, remove_from=self) for n in l1))
        elif l2 and not l1:
            yield CompoundEdit(from_node=self, to_node=node, edits=(Insert(n, insert_into=self) for n in l2))
        else:
            for possibility in self._match(node, l1[1:], l2):
                yield CompoundEdit(from_node=self, to_node=node, edits=iter((Remove(l1[0], remove_from=self), possibility)))
            for possibility in self._match(node, l1, l2[1:]):
                yield CompoundEdit(from_node=self, to_node=node, edits=iter((Insert(l2[0], insert_into=self), possibility)))
            matches: List[Edit] = [Replace(l1[0], l2[0]), l1[0].edits(l2[0])]
            if len(l1) == 1 and len(l2) == 1:
                yield from iter(matches)
            else:
                possibilities = self._match(node, l1[1:], l2[1:])
                for pair in itertools.product(matches, possibilities):
                    yield CompoundEdit(from_node=self, to_node=node, edits=iter(pair))

    def calculate_total_size(self):
        return sum(c.total_size for c in self.children)

    def __len__(self):
        return len(self.children)

    def __iter__(self) -> Iterator[TreeNode]:
        return iter(self.children)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.children!r})"

    def __str__(self):
        return str(self.children)


class DictNode(ListNode):
    def __init__(self, dict_like: Dict[LeafNode, TreeNode]):
        super().__init__(sorted(KeyValuePairNode(key, value) for key, value in dict_like.items()))


class StringNode(LeafNode):
    def __init__(self, string_like: str):
        super().__init__(string_like)


class IntegerNode(LeafNode):
    def __init__(self, int_like: int):
        super().__init__(int_like)


class InitialState(Edit):
    def __init__(self, tree1_root: TreeNode, tree2_root: TreeNode):
        super(tree1_root, tree2_root)

    def cost(self):
        return Range(0, 0)


class Match(Edit):
    def __init__(self, match_from: TreeNode, match_to: TreeNode, cost: int):
        super().__init__(
            from_node=match_from,
            to_node=match_to,
            constant_cost=cost,
            cost_upper_bound=cost
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(match_from={self.from_node!r}, match_to={self.to_node!r}, cost={self.cost().lower_bound!r})"


class Replace(Edit):
    def __init__(self, to_replace: TreeNode, replace_with: TreeNode):
        cost = max(to_replace.total_size, replace_with.total_size) + 1
        super().__init__(
            from_node=to_replace,
            to_node=replace_with,
            constant_cost=cost,
            cost_upper_bound=cost
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(to_replace={self.from_node!r}, replace_with={self.to_node!r})"


class Remove(Edit):
    def __init__(self, to_remove: TreeNode, remove_from: TreeNode):
        super().__init__(
            from_node=to_remove,
            to_node=remove_from,
            constant_cost=to_remove.total_size + 1,
            cost_upper_bound=to_remove.total_size + 1
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({self.from_node!r}, remove_from={self.to_node!r})"


class Insert(Edit):
    def __init__(self, to_insert: TreeNode, insert_into: TreeNode):
        super().__init__(
            from_node=to_insert,
            to_node=insert_into,
            constant_cost=to_insert.total_size + 1,
            cost_upper_bound=to_insert.total_size + 1
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(to_insert={self.from_node!r}, insert_into={self.to_node!r})"


AtomicEdit = Union[Insert, Remove, Replace, Match]


def explode_edits(edit: Edit) -> Iterator[AtomicEdit]:
    if isinstance(edit, CompoundEdit):
        for sub_edit in edit.sub_edits:
            yield from explode_edits(sub_edit)
    elif isinstance(edit, PossibleEdits):
        while not edit.cost().definitive():
            if not edit.tighten_bounds():
                break
        if edit.best_possibility is None:
            yield edit
        else:
            yield from explode_edits(edit.best_possibility)
    else:
        yield edit


class Diff:
    def __init__(self, from_root: TreeNode, to_root: TreeNode, edits: Iterable[Edit]):
        self.from_root = from_root
        self.to_root = to_root
        self.edits: Tuple[AtomicEdit] = tuple(itertools.chain(*(explode_edits(edit) for edit in edits)))

    def cost(self) -> int:
        return sum(e.cost().upper_bound for e in self.edits)

    def __repr__(self):
        return f"{self.__class__.__name__}(from_root={self.from_root!r}, to_root={self.to_root!r}, edits={self.edits!r})"


def diff(tree1_root: TreeNode, tree2_root: TreeNode) -> Diff:
    return Diff(tree1_root, tree2_root, (tree1_root.edits(tree2_root),))


def build_tree(python_obj, force_leaf_node=False) -> TreeNode:
    if isinstance(python_obj, int):
        return IntegerNode(python_obj)
    elif isinstance(python_obj, str) or isinstance(python_obj, bytes):
        return StringNode(python_obj)
    elif force_leaf_node:
        raise ValueError(f"{python_obj!r} was expected to be an int or string, but was instead a {type(python_obj)}")
    elif isinstance(python_obj, list) or isinstance(python_obj, tuple):
        return ListNode([build_tree(n) for n in python_obj])
    elif isinstance(python_obj, dict):
        return DictNode({
            build_tree(k, force_leaf_node=True): build_tree(v) for k, v in python_obj.items()
        })
    else:
        raise ValueError(f"Unsupported Python object {python_obj!r} of type {type(python_obj)}")


if __name__ == '__main__':
    obj1 = build_tree({
        "test": "foo",
        "baz": 1
    })
    obj2 = build_tree({
        "test": "bar",
        "baz": 2
    })

    edits = diff(obj1, obj2)
    print(edits.cost())
    print(edits)
