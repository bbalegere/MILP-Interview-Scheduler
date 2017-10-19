import argparse
from datetime import datetime

import numpy as np
import pandas as pd
from gurobipy import *


def read_input_csv(filename, typ=None):
    sldf = pd.read_csv(filename, index_col=0, header=0, dtype=typ)
    return sldf.to_dict('index'), sorted(sldf.columns.values), list(sldf.index.values)


def read_slots_interviews(filename):
    sidict = pd.read_csv(filename, dtype=object).to_dict('list')
    return dict((key, int(v[0])) for key, v in sidict.items())


def read_shortlists(filename):
    sldf = pd.read_csv(filename, dtype=object)
    comps = list(sldf.columns.values)
    comtupl, shdict = multidict(((c, n), 1) for c in comps for n in list(sldf[c].dropna().values))
    return dict((x, 1) for x in comtupl), comps, sorted(set([x[1] for x in comtupl]))


def read_gdPanels(filename):
    gdcomp = set()
    with open(filename) as f:
        for csvline in f:
            gdcomp.add(tuple([x for x in csvline.strip().split(',') if x]))

    return gdcomp


def read_lp(filename):
    exnames = []
    with open(filename) as f:
        for csvline in f:
            exnames = exnames + [x for x in csvline.strip().split(',') if len(str(x).strip()) > 0]

    return sorted(set(exnames))


def generateSchedule(companies, fixedints, names, panels, shortlists, slots, slots_int, gdpanels):
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
    compnames = tuplelist(shortlists.keys())
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

    # Constraint - Fix manually given schedule
    for idx, val in fixedints.items():
        for idx2, n in val.items():
            if n in names:
                model.addConstr(choices[idx, idx2, n], GRB.EQUAL, 1)

    print('Optimising')
    model.optimize()
    solution = model.getAttr('X', choices)
    schedout = open('schedule.csv', 'w')
    line = 'Slot'
    for c in companies:
        for j in range(int(maxpanels[c])):
            line = line + ',' + c + str(j + 1)
    schedout.write(line + '\n')
    for s in slots:
        line = s
        for c in companies:
            row = [''] * int(maxpanels[c])
            i = 0
            for x, n in compnames.select(c, '*'):
                if solution[s, c, n] == 1:
                    row[i] = n
                    i = i + 1

            line = line + ',' + ','.join(row)

        schedout.write(line + '\n')
    schedout.close()
    namesout = open('names.csv', 'w')
    line = 'Slot'
    for n in names:
        line = line + ',' + n
    namesout.write(line + '\n')
    for s in slots:
        line = s
        for n in names:
            row = ''
            for c, x in compnames.select('*', n):
                if solution[s, c, n] == 1:
                    row = c

            line = line + ',' + row

        namesout.write(line + '\n')
    namesout.close()
    print(model.status)
    print(datetime.now().time())
    bufferout = open('bufferlist.csv', 'w')
    for c in gdpanels:
        line = c[0]
        for n in buffernames:
            if shortlists.get((c[0], n), 0) > 0:
                line = line + ',' + n

        bufferout.write(line + '\n')

    bufferout.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('shortlists', help='Shortlists File as CSV', metavar='Shortlists.csv')
    parser.add_argument('slotspanels', help='Slots and Panels as CSV', metavar='SlotsPanels.csv')
    parser.add_argument('slotsgd', help='Number of Slots required for the GD', metavar='SlotsGG.csv')
    parser.add_argument('gdslots', help='CSV containing dummy company names indicating different panels', metavar='GDSlots.csv')
    parser.add_argument('-l', '--leftprocess', help='CSV with a list of candidates who have left the process', metavar='lp.csv')
    parser.add_argument('-f', '--fixed', help='CSV of the schedule with pre fixed candidates. Should satisfy constraints', metavar='fixed.csv')

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

    generateSchedule(companies, fixedints, names, panels, shortlists, slots, slots_int, gdpanels)
