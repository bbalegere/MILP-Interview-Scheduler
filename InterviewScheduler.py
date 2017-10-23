import argparse
from datetime import datetime

import numpy as np
import pandas as pd
from gurobipy import *


def read_input_csv(filename, typ=None):
    sldf = pd.read_csv(filename, header=0, dtype=typ)
    sldf[sldf.columns[0]] = sldf[sldf.columns[0]].astype(str)
    sldf.set_index(sldf.columns[0], inplace=True)
    return sldf.to_dict('index'), sorted(sldf.columns.values), list(sldf.index.values)


def read_slots_interviews(filename):
    sidict = pd.read_csv(filename, dtype=object).to_dict('list')
    return dict((key, int(v[0])) for key, v in sidict.items())


def read_shortlists(filename):
    sldf = pd.read_csv(filename, dtype=object)
    comps = list(sldf.columns.values)
    comtupl = [(c, n) for c in comps for n in list(sldf[c].dropna().values)]
    return dict((x, 1) for x in comtupl), comps, sorted(set([x[1] for x in comtupl]))


def read_lp(filename):
    exnames = []
    with open(filename) as f:
        for csvline in f:
            exnames = exnames + [str(x).strip() for x in csvline.strip().split(',') if len(str(x).strip()) > 0]

    return sorted(set(exnames))


def generateSchedule(companies, fixedints, names, panels, prefs, shortlists, slots, slots_int, out):
    print(datetime.now().time())
    # Find out max number of panels
    maxpanels = dict((c, max(panels[s][c] for s in slots)) for c in companies)
    # Generate cost of slots
    costs = dict((slots[s], s + 1) for s in range(len(slots)))
    # Calculate number shortlists for each students
    crit = dict((n, sum(shortlists.get((c, n), 0) for c in companies)) for n in names)
    # Remove names who dont have any shortlists
    names = [key for key, value in crit.items() if value > 0]
    # Calculate number shortlists per company
    compshortlists = dict((c, sum(shortlists.get((c, n), 0) for n in names)) for c in companies)
    # Calculate total number of panels per company
    comppanels = dict((c, int(sum(panels[s][c] for s in slots) / slots_int.get(c, 1))) for c in companies)

    for c in companies:
        if compshortlists[c] > comppanels[c]:
            print(c + " has shortlists greater than no of panels " + str(compshortlists[c]) + " > " + str(comppanels[c]))

    fibonacii = [2, 3]
    for i in range(2, 1 + int(max(crit.values()))):
        fibonacii.append(fibonacii[i - 1] + fibonacii[i - 2])

    # Create Objective Coefficients
    prefsnew = dict()
    objcoeff = dict()

    if len(prefs):

        for n in names:
            actpref = dict((c, prefs[n][c] * shortlists.get((c, n), 0)) for c in companies if shortlists.get((c, n), 0) > 0)
            scaledpref = {key: rank for rank, key in enumerate(sorted(actpref, key=actpref.get), 1)}

            for c, rank in scaledpref.items():
                prefsnew[n, c] = rank
                for s in slots:
                    if compshortlists[c] > comppanels[c]:
                        objcoeff[s, c, n] = (rank / (crit[n] + 1)) * (len(slots) + 1 - costs[s])
                    else:
                        objcoeff[s, c, n] = (1 - rank / (crit[n] + 1)) * costs[s]

        pd.DataFrame([(k[0], k[1], v) for k, v in prefsnew.items()]).to_csv(out+"\\prefsupload.csv", header=False, index=False)

    print('Creating IPLP')
    model = Model('interviews')
    compnames = tuplelist([(c, n) for c, n in shortlists.keys() if n in names])
    choices = model.addVars(slots, compnames, vtype=GRB.BINARY, name='G')
    # Objective - allocate max students to the initial few slots
    model.setObjective(quicksum(choices[s, c, n] * objcoeff.get((s, c, n), costs[s]) for s in slots for c, n in compnames), GRB.MINIMIZE)
    # Constraint - maximum number in a slot for a club is limited by panels
    model.addConstrs((choices.sum(s, c, '*') <= panels[s][c] for s in slots for c in companies))
    # Constraint - allocate student only if he has a shortlist
    model.addConstrs((choices.sum('*', c, n) <= shortlists.get((c, n), 0) * slots_int.get(c, 1) for n in names for c in companies))
    # Constraint - slots should not conflict for a student
    model.addConstrs((choices.sum(s, '*', n) <= 1 for s in slots for n in names))
    # Constraint - allocate all students or number of interviews possible
    model.addConstrs((choices.sum('*', c, '*') == min(compshortlists[c], comppanels[c]) * slots_int.get(c, 1) for c in companies))
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
    flist = [(s, c, n) for s, vals in fixedints.items() for c, n in vals.items() if (c, n) in compnames]
    model.addConstrs((choices[s, c, n] == 1 for s, c, n in flist))

    print('Optimising')
    model.optimize()
    solution = model.getAttr('X', choices)

    sche = [['Slot'] + [c + str(j + 1) for c in companies for j in range(int(maxpanels[c]))]]

    for s in slots:
        temp = [s]
        for c in companies:
            row = [''] * int(maxpanels[c])
            i = 0
            for n in [name for com, name in compnames if com == c]:
                if solution.get((s, c, n), 0):
                    row[i] = n + ' ' + str(int(prefsnew.get((n, c), 0))) + '_' + str(int(crit[n]))
                    i = i + 1
            temp = temp + row
        sche.append(temp)

    schedf = pd.DataFrame(sche)
    schedf.to_csv(out+'\\sche.csv', index=False, header=False)

    namesdf = pd.DataFrame.from_dict(dict((s, {n: (c + ' ' + str(int(prefsnew.get((n, c), 0))) + '_' + str(int(crit[n]))) for c in companies for n in
                                               names if solution.get((s, c, n), 0)}) for s in slots), orient='index')
    namesdf.sort_index(axis=1).to_csv(out+'\\names.csv')

    pd.DataFrame([(n, c, 1, 1) for c in companies for n in names if solution.get((slots[0], c, n), 0)],
                 columns=['Name', 'Company', 'Round', 'Panel']).to_csv(out+'\\staticupload.csv', index=False)

    print(model.status)
    print(datetime.now().time())

    if prefsnew:
        unordn = set()
        for n in names:
            init = 1
            for s in slots:
                stop = False
                for c in companies:
                    if solution.get((s, c, n), 0) == 1:
                        if prefsnew[n, c] < init:
                            unordn.add(n)
                            stop = True
                            break
                        else:
                            init = prefsnew[n, c]

                if stop:
                    break
        print('The following candidates preference order has been violated')
        print(unordn)
        print(len(unordn))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('shortlists', help='Shortlists File per company as CSV', metavar='Shortlists.csv')
    parser.add_argument('slotspanels', help='Slots and Panels per company as CSV', metavar='SlotsPanels.csv')
    parser.add_argument('slotsint', help='Number of Slots required per Interview for each company', metavar='SlotsInterview.csv')
    parser.add_argument('-p', '--prefs', help='CSV with a matrix containing names and companies', metavar='prefs.csv')
    parser.add_argument('-l', '--leftprocess', help='CSV with a list of candidates who have left the process', metavar='lp.csv')
    parser.add_argument('-f', '--fixed', help='CSV of the schedule with pre fixed candidates. Should satisfy constraints', metavar='fixed.csv')
    parser.add_argument('-o', '--output', help='Output directory', default='out')

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

    slots_int = read_slots_interviews(args.slotsint)
    assert (sorted(slots_int.keys()) == sorted(companies))

    lp = list()
    if args.leftprocess:
        lp = read_lp(args.leftprocess)
        names = [n for n in names if n not in lp]

    prefs = dict()

    if args.prefs:
        prefs, comps3, names2 = read_input_csv(args.prefs)
        for vals in prefs.values():
            for val in vals.values():
                if val not in range(1, len(companies) + 1):
                    raise ValueError('Incorrect preference ' + str(val) + '. It should be between 1 and ' + str(len(companies)))
        assert (sorted(companies) == sorted(comps3))

        missing = set(names) - set(names2)
        if len(missing):
            print('Preferences are missing for below names')
            print(missing)
            raise ValueError('Some names are mssing')

    fixedints = dict()
    if args.fixed:
        fixedints, clubs4, slots2 = read_input_csv(args.fixed, typ=object)


    if not os.path.exists(args.output):
        os.makedirs(args.output)

    generateSchedule(companies, fixedints, names, panels, prefs, shortlists, slots, slots_int, args.output)
