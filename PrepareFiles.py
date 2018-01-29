"""
    Author: Bharat Balegere
    Date created: 10-Oct-2017
    Date last modified: 23-Jan-2018
    Python Version: 3.6
"""
import argparse

import pandas as pd

if __name__ == "__main__":

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('shortlists', help='Shortlists File as CSV', metavar='Shortlists.csv')
    parser.add_argument('gdslots', help='GD Slots and Panels as CSV', metavar='GDSlotsPanels.csv')
    parser.add_argument('-e', '--effective', help='Read effective shortlists', action='count', default=0)
    args = parser.parse_args()

    shortlistdf = pd.read_csv(args.shortlists, dtype=object)
    print(shortlistdf.info())
    if args.effective:
        shl = list(shortlistdf[['process', 'Company']].values)
        shortlistdf = pd.DataFrame({c: pd.Series([n for n, x in shl if x == c]) for y, c in shl})

    gdslots = pd.read_csv(args.gdslots)
    gddict = gdslots.to_dict('list')
    print(gdslots.info())
    companies = list(gdslots.columns.values)
    shortlistdf = shortlistdf[companies]
    gdcomps = []
    slotspanels = []
    comps = []
    slotsrow = []
    slotsint = []
    defaultslots = 3
    for c in companies:
        comp = [c]
        comps.append(c)
        slotsrow.append(gdslots.get_value(1, c))
        slotsint.append(gdslots.get_value(2, c))
        for i in range(1, gdslots.get_value(0, c)):
            compval = c + str(i + 1)
            shortlistdf[compval] = shortlistdf[c]
            comp.append(compval)
            comps.append(compval)
            slotsrow.append(gdslots.get_value(1, c))
            slotsint.append(gdslots.get_value(2, c))

        gdcomps.append(comp)
    shortlistdf.sort_index(axis=1, inplace=True)
    shortlistdf.to_csv('RawShortlists.csv', index=False)

    gdcompdf = pd.DataFrame(gdcomps)
    gdcompdf.to_csv('GDPanels.csv', index=False, header=False)

    slotspanels.append(['Slots'] + comps)
    for i in range(35):
        val = "Slots_%02d" % i
        slotspanels.append([val] + slotsrow)

    slotsdf = pd.DataFrame(slotspanels)
    slotsdf.to_csv('SlotsPanels.csv', index=False, header=False)

    slotsint2 = [comps, slotsint]
    slotsintdf = pd.DataFrame(slotsint2)
    slotsintdf.to_csv('SlotsInterview.csv', index=False, header=False)
