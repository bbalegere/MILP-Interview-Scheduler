import argparse
from string import punctuation

import pandas as pd

table = str.maketrans({key: None for key in punctuation})


def read_input_csv(filename, typ=None):
    sldf = pd.read_csv(filename, header=0, dtype=typ)
    sldf.columns = sldf.columns.str.strip().str.lower().str.replace(' ', '_').str.translate(table)
    sldf[sldf.columns[0]] = sldf[sldf.columns[0]].astype(str).str.strip().str.lower().str.replace(' ', '_')
    sldf.set_index(sldf.columns[0], inplace=True)
    return sldf.to_dict('index'), sorted(sldf.columns.values), list(sldf.index.values)


def read_slots_interviews(filename):
    sidf = pd.read_csv(filename, dtype=object)
    sidf.columns = sidf.columns.str.strip().str.lower().str.replace(' ', '_').str.translate(table)
    sidict = sidf.to_dict('list')
    return dict((key, int(v[0])) for key, v in sidict.items())


def read_shortlists(filename):
    sldf = pd.read_csv(filename, dtype=object)
    sldf.columns = sldf.columns.str.strip().str.lower().str.replace(' ', '_').str.translate(table)
    comps = list(sldf.columns.values)
    comtupl = [(c, str(n).strip().lower().replace(' ', '_')) for c in comps for n in list(sldf[c].dropna().values)]
    return dict((x, 1) for x in comtupl), sorted(comps), sorted(set([x[1] for x in comtupl]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('shortlists', help='Shortlists File per company as CSV', metavar='Shortlists.csv')
    parser.add_argument('prefs', help='CSV with a matrix containing names and companies', metavar='prefs.csv')

    args = parser.parse_args()
    shortlists, shcompanies, names = read_shortlists(args.shortlists)

    prefs, comps3, names2 = read_input_csv(args.prefs)
    for vals in prefs.values():
        for val in vals.values():
            if val not in range(1, len(shcompanies) + 1):
                raise ValueError('Incorrect preference ' + str(val) + '. It should be between 1 and ' + str(len(shcompanies)))

    print(set(shcompanies) ^ set(comps3))
    assert (shcompanies == comps3)

    missing = set(names) - set(names2)
    if len(missing):
        print('Preferences are missing for below names')
        print(missing)
        raise ValueError('Some names are mssing')

    prefsnew = dict()
    for n in names:
        actpref = dict((c, prefs[n][c] * shortlists.get((c, n), 0)) for c in shcompanies if shortlists.get((c, n), 0) > 0)
        scaledpref = {key: rank for rank, key in enumerate(sorted(actpref, key=actpref.get), 1)}

        for c, rank in scaledpref.items():
            prefsnew[n, c] = rank

    pd.DataFrame([(k[0], k[1], v) for k, v in prefsnew.items()]).to_csv("prefsupload.csv", header=False, index=False)
