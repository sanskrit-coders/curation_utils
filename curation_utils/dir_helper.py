import json

# Remove all handlers associated with the root logger object.
import logging

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


class Node(dict):

    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, val):
        self[attr] = val

    def __missing__(self, key):
        value = self[key] = type(self)() # retain local pointer to value
        return value                     # faster to return than dict lookup

    def add_path(self, path):
        t = self
        for node in path:
            t = t[node]

    def rename_key(self, key, new_key):
        self[new_key] = self.pop(key, None)

    def set_ordinals(self, ordinal_format="%02d_"):
        keys = list(self.keys())
        for key_index in range(0, len(keys)):
            key = keys[key_index]
            new_key = ordinal_format % (key_index + 1) + key
            self.rename_key(key=key, new_key=new_key)
        
        for key in self.keys():
            self[key].set_ordinals()

    def make_dirs(self, base_dir, dry_run=False):
        import os
        for key in self.keys():
            child_path = os.path.join(base_dir, key)
            if not dry_run:
                os.makedirs(child_path, exist_ok=True)
            else:
                logging.info(child_path)
            self[key].make_dirs(base_dir=child_path, dry_run=dry_run)

    def regularize_keys(self, regularizer=None):
        if regularizer is None:
            from indic_transliteration import sanscript
            regularizer = lambda key: sanscript.transliterate(key, sanscript.DEVANAGARI, sanscript.OPTITRANS).replace(" ", "_")
        keys = list(self.keys())
        for key in keys:
            import regex
            key = regex.sub("\s+", " ", key)
            new_key = regularizer(key)
            self.rename_key(key=key, new_key=new_key)
            self[new_key].regularize_keys(regularizer=regularizer)

    def __str__(self):
        return json.dumps(self, indent=2, ensure_ascii=False)


def tree_from_lines(lines, indent_string="  "):
    lines = iter(lines)
    path = ["root"]
    root_node = Node()
    from itertools import takewhile
    for line in lines:
        line = line.replace(indent_string, "\t")
        indent = len(list(takewhile('\t'.__eq__, line))) + 1
        path[indent:] = [line.strip()]
        root_node.add_path(path=path)
    return root_node


def tree_from_file(file_path, indent_string="  "):
    with open(file_path) as dirfile:
        root_node = tree_from_lines(lines=dirfile.readlines(), indent_string=indent_string)
        return root_node
