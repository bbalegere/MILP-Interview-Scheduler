"""
    Author: Bharat Balegere
    Date created: 10-Oct-2017
    Date last modified: 23-Jan-2018
    Python Version: 3.6
"""
import argparse
from datetime import datetime
from string import punctuation

import numpy as np
import pandas as pd
from gurobipy import *

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


def read_gdPanels(filename):
    gdcomp = set()
    with open(filename) as f:
        for csvline in f:
            gdcomp.add(tuple([str(x).strip().lower().replace(' ', '_').translate(table) for x in csvline.strip().split(',') if x]))

    return gdcomp


def read_lp(filename):
    exnames = []
    with open(filename) as f:
        for csvline in f:
            exnames = exnames + [str(x).strip().lower().replace(' ', '_') for x in csvline.strip().split(',') if len(str(x).strip()) > 0]

    return sorted(set(exnames))


def generateSchedule(companies, fixedints, names, panels, shortlists, slots, slots_int, gdpanels, skipinitial, out):
    print(datetime.now().time())
    # Find out max number of panels
    maxpanels = dict((c, max(panels[s][c] for s in slots)) for c in companies)
    # Generate cost of slots
    costs = dict((slots[s], s + 1) for s in range(len(slots)))
    # Calculate number shortlists for each students
    crit = dict((n, sum(shortlists.get((c, n), 0) for c in companies)) for n in names)
    # Remove names who dont have any shortlists
    names = [key for key, value in crit.items() if value > 2]
    buffernames = [key for key, value in crit.items() if value <= 2]
    # Calculate number shortlists per company
    compshortlists = dict((c, sum(shortlists.get((c, n), 0) for n in names)) for c in companies)
    # Calculate total number of panels per company
    comppanels = dict((g[0], int(sum(panels[s][c] for s in slots for c in g) / slots_int.get(g[0], 1))) for g in gdpanels)

    for c in gdpanels:
        if compshortlists[c[0]] > comppanels[c[0]]:
            print(c[0] + " has shortlists greater than no of panels " + str(compshortlists[c[0]]) + " > " + str(comppanels[c[0]]))

    print('Creating IPLP')
    model = Model('interviews')
    compnames = tuplelist([(c, n) for c, n in shortlists.keys() if n in names])
    choices = model.addVars(slots, compnames, vtype=GRB.BINARY, name='G')
    # Objective - allocate max students to the initial few slots
    model.setObjective(quicksum(choices[s, c, n] * costs[s] for s in slots for c, n in compnames), GRB.MINIMIZE)
    # Constraint - maximum number in a slot for a club is limited by panels
    model.addConstrs((choices.sum(s, c, '*') <= panels[s][c] for s in slots for c in companies))
    # Constraint - allocate student only if he has a shortlist
    model.addConstrs((choices.sum('*', c, n) <= shortlists.get((c[0], n), 0) * slots_int.get(c[0], 1) for n in names for c in gdpanels))
    # Constraint - slots should not conflict for a student
    model.addConstrs((choices.sum(s, '*', n) <= 1 for s in slots for n in names))
    # Constraint - allocate all students or number of interviews possible
    model.addConstrs((choices.sum('*', c, '*') == min(compshortlists[c[0]], comppanels[c[0]]) * slots_int.get(c[0], 1) for c in gdpanels))
    # Constraint - for multiple slots per interview, same candidate should be allocated
    for c, si in slots_int.items():

        start_slot = 0
        while panels[slots[start_slot]][c] == 0:
            start_slot += 1

        if si > 1:
            for i in range(si - 1 + start_slot, len(slots), si):
                for x, n in compnames.select(c, '*'):
                    for j in range(i - si + 1, i):
                        model.addConstr((choices[slots[i], c, n] - choices[slots[j], c, n]), GRB.EQUAL, 0)

    flist = [(s, c, n) for s, vals in fixedints.items() for c, n in vals.items() if (c, n) in compnames]
    model.addConstrs((choices[s, c, n] == 1 for s, c, n in flist))

    model.addConstrs((choices.sum(slots[0], c, n) == 0 for c in companies for n in skipinitial))

    print('Optimising')
    model.optimize()
    solution = model.getAttr('X', choices)

    sche = [['Slot'] + [c for c in companies for j in range(int(maxpanels[c]))]]

    for s in slots:
        temp = [s]
        for c in companies:
            row = [''] * int(maxpanels[c])
            i = 0
            for n in [name for com, name in compnames if com == c]:
                if solution.get((s, c, n), 0):
                    row[i] = n
                    i = i + 1
            temp = temp + row
        sche.append(temp)

    schedf = pd.DataFrame(sche)
    schedf.to_csv(out + '\\sche.csv', index=False, header=False)

    namesdf = pd.DataFrame.from_dict(dict((s, {n: c for c in companies for n in names if solution.get((s, c, n), 0)}) for s in slots), orient='index')
    namesdf.sort_index(axis=1).to_csv(out + '\\names.csv')

    pd.DataFrame([[c[0]] + [n for n in buffernames if shortlists.get((c[0], n), 0)] for c in gdpanels]).to_csv(out + '\\buff.csv', index=False,
                                                                                                               header=False)

    tl = [(n, c[0], 1, i + 1) for c in gdpanels for i, dc in enumerate(c) for n in names if solution.get((slots[0], dc, n), 0)]

    sl = pd.DataFrame(tl, columns=['Name', 'Company', 'Round', 'Panel'])
    sl.sort_values(['Company', 'Panel']).to_csv(out + '\\staticupload.csv', index=False)
    print(model.status)
    print(datetime.now().time())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('shortlists', help='Shortlists File as CSV', metavar='Shortlists.csv')
    parser.add_argument('slotspanels', help='Slots and Panels as CSV', metavar='SlotsPanels.csv')
    parser.add_argument('slotsgd', help='Number of Slots required for the GD', metavar='SlotsGG.csv')
    parser.add_argument('gdslots', help='CSV containing dummy company names indicating different panels', metavar='GDSlots.csv')
    parser.add_argument('-l', '--leftprocess', help='CSV with a list of candidates who have left the process', metavar='lp.csv')
    parser.add_argument('-f', '--fixed', help='CSV of the schedule with pre fixed candidates. Should satisfy constraints', metavar='fixed.csv')
    parser.add_argument('-o', '--output', help='Output directory', default='out')
    parser.add_argument('-s', '--skipinitial', help='Skip initial few slots', metavar='skip.csv')

    args = parser.parse_args()
    shortlists, companies, names = read_shortlists(args.shortlists)
    panels, comp2, slots = read_input_csv(args.slotspanels)
    print('Number of Companies')
    print(len(companies))
    print('Number of Candidates')
    print(len(names))
    print('Number of Slots')
    print(len(slots))
    assert (sorted(companies) == sorted(comp2))

    if len([x for vals in panels.values() for x in vals.values() if not np.issubdtype(x, int) or x < 0]):
        raise ValueError('The number of panels must be a positive integer ')

    slots_int = read_slots_interviews(args.slotsgd)
    assert (sorted(slots_int.keys()) == sorted(companies))

    gdpanels = read_gdPanels(args.gdslots)
    gdcomps = [y for x in gdpanels for y in x]
    assert (sorted(companies) == sorted(gdcomps))

    fixedints = dict()
    if args.fixed:
        fixedints, clubs4, slots2 = read_input_csv(args.fixed, typ=object)

    lp = list()
    if args.leftprocess:
        lp = read_lp(args.leftprocess)
        names = [n for n in names if n not in lp]

    skip = list()
    if args.skipinitial:
        skip = read_lp(args.skipinitial)

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    generateSchedule(companies, fixedints, names, panels, shortlists, slots, slots_int, gdpanels, skip, args.output)
