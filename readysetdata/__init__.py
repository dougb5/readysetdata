import sys
from pathlib import Path

debug = '--debug' in sys.argv


class AttrDict(dict):
    'Augment a dict with more convenient .attr syntax.  not-present keys return None.'
    def __getattr__(self, k):
        try:
            v = self[k]
            if isinstance(v, dict) and not isinstance(v, AttrDict):
                v = AttrDict(v)
            return v
        except KeyError:
            if k.startswith("__"):
                raise AttributeError
            return None


class Progress:
    def __init__(self, iterator, name=''):
        self.iterator = iterator
        self.name = name

    def __iter__(self):
        for i, x in enumerate(self.iterator):
            yield x
            if i % 10000 == 0:
                print(f'\r{self.name} {i}', end='', file=sys.stderr)
                sys.stderr.flush()
                if debug and i:
                    break

        print('', file=sys.stderr)


def get_optarg(arg):
    try:
        i = sys.argv.index(arg)
        return sys.argv[i+1]
    except ValueError:
        return ''

## extract

def unzip_text(p, fn):
    import zipfile
    import io
    zf = zipfile.ZipFile(p)
    fp = zf.open(fn, 'r')
    return io.TextIOWrapper(fp, 'utf-8')


def unzip(p):
#    from stream_unzip import stream_unzip
    import zipfile
    return zipfile.ZipFile(p)


## parse

def parse_csv(fp):
    import csv
    for r in Progress(csv.DictReader(fp)):
        yield AttrDict(r)


def parse_asv(fp, delim='\t'):
    it = iter(fp)
    hdrs = next(it).split(delim)

    for line in Progress(it):
        yield AttrDict(zip(hdrs, line.split(delim)))


class JsonLines:
    def __init__(self, fp):
        self.fp = fp

    def __iter__(self):
        import json

        for line in self.fp:
            yield AttrDict(json.loads(line))


def parse_jsonl(fp):
    return JsonLines(fp)

## output

def batchify(rows, n=10000):
    rowbatch = []
    for row in rows:
        rowbatch.append(row)
        if len(rowbatch) >= n:
            yield rowbatch
            rowbatch = []

    if rowbatch:
        yield rowbatch


def output(dbname, tblname, rows, schemastr=''):
    fmtstr = get_optarg('-f')

    if fmtstr:
        fmts = fmtstr.split(',')
    else:
        fmts = [func.removeprefix('output_')
                  for func in globals()
                    if func.startswith('output_')]

    outdir = get_optarg('-o') or '.'
    Path(outdir).mkdir(parents=True, exist_ok=True)

    dbpath = str(Path(outdir)/dbname)

    outputters = []

    for i, rowbatch in enumerate(batchify(rows)):
        if i == 0:  # first batch
            if not schemastr:
                schemastr = ' '.join(rowbatch[0].keys())

            outputters = [
                globals()[f'output_{fmt}'](dbpath, tblname, schemastr)
                    for fmt in fmts
            ]
        for outputter in outputters:
            batchrows = [list(r.values()) for r in rowbatch]
            outputter.output_batch(batchrows)

    for outputter in outputters:
        outputter.finalize()


from .download import *

from .arrow import *
from .parquet import *
from .duckdb import *
from .http_unzip import *