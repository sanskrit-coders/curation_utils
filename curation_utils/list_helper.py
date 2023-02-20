from collections import OrderedDict

def split_into_n_bits(list_in, n):
    k, m = divmod(len(list_in), n)
    return (list_in[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

def divide_chunks(list_in, n):
    # looping till length l 
    for i in range(0, len(list_in), n):
        yield list_in[i:i + n]

class OrderedDefaultDict(OrderedDict): #name according to default
    def __init__(self, default_fn):
        self.default_fn = default_fn

    def __missing__(self, key):
        self[key] = value = self.default_fn()
        return value
