

import copy
import os

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.externals import joblib
from sklearn import cross_validation


from object_conversions.conversion_to_histo import function2th2
from identification_isolation import efficiency

from rootpy.plotting import Hist2D, Hist3D
from rootpy.io import root_open
from root_numpy import root2array



# Predefined binning to store regression results
binning = {}
binning['abs(ieta)'] = (30, 0.5, 30.5)
binning['et'] = (400, 0.5, 400.5)
binning['rho'] = (500, 0., 50)
binning['ntt'] = (81, -0.5, 80.5)

def fit(filename, treename, inputsname, targetname, workingpoint=0.9, test=False):
    # Reading inputs and targets
    ninputs = len(inputsname)
    branches = copy.deepcopy(inputsname)
    branches.append(targetname)
    data = root2array(filename, treename=treename, branches=branches)
    data = data.view((np.float64, len(data.dtype.names)))
    # Extract and format inputs and targets from numpy array
    inputs = data[:, range(ninputs)].astype(np.float32)
    targets = data[:, [ninputs]].astype(np.float32).ravel()
    # if test requested, use 60% of events for training and 40% for testing
    inputs_train = inputs
    targets_train = targets
    if test:
        inputs_train, inputs_test, targets_train, targets_test = cross_validation.train_test_split(inputs, targets, test_size=0.4, random_state=0)
    # Define and fit quantile regression (quantile = workingpoint)
    # Default training parameters are used
    regressor = GradientBoostingRegressor(loss='quantile', alpha=workingpoint)
    regressor.fit(inputs_train, targets_train)
    if test:
        # Compare regression prediction with the true value and count the fraction of time it falls below
        # This should give the working point value
        predict_test = regressor.predict(inputs_test)
        compare = np.less(targets_test, predict_test)
        print 'Testing regression with inputs', inputsname, 'and working point', workingpoint
        print '    Test efficiency =', float(list(compare).count(True))/float(len(compare))
        # TODO: add 1D efficiency graphs vs input variables
    return regressor

def store(regressor, name, inputs, outputfile):
    # Save scikit-learn regression object  
    result_dir = outputfile.GetName().replace('.root','')
    if not os.path.exists(result_dir): os.mkdir(result_dir)
    joblib.dump(regressor, result_dir+'/'+name+'.pkl') 
    # Save result in ROOT histograms if possible
    if len(inputs)!=2 and len(inputs)!=3:
        print 'The regression result will not be stored in a ROOT histogram. Only 2D or 3D histograms can be stored for the moment.'
        return
    for input in inputs:
        if not input in binning:
            print 'Binning is not defined for variable '+input+'. Please add it in quantile_regression.binning if you want to store results in histograms'
            return
    if len(inputs)==2:
        histo = function2th2(regressor.predict, binning[inputs[0]], binning[inputs[1]])
    elif len(inputs)==3:
        histo = Hist3D(*(binning[inputs[0]]+binning[inputs[1]]+binning[inputs[2]]), name=name)
        histo.SetXTitle(inputs[0])
        histo.SetYTitle(inputs[1])
        histo.SetZTitle(inputs[2])
        for bx in histo.bins_range(0):
            x = histo.GetXaxis().GetBinCenter(bx)
            for by in histo.bins_range(1):
                y = histo.GetYaxis().GetBinCenter(by)
                for bz in histo.bins_range(2):
                    z = histo.GetZaxis().GetBinCenter(bz)
                    histo[bx,by,bz].value = regressor.predict([[x,y,z]])
    outputfile.cd()
    histo.Write()


def main(inputfile, tree, inputs, target, outputfile, name, eff=0.9, test=False):
    regressor = fit(filename=inputfile, treename=tree, inputsname=inputs, targetname=target, workingpoint=eff, test=test)
    if os.path.splitext(outputfile)[1]!='.root': outputfile += '.root'
    with root_open(outputfile, 'recreate') as output_file:
        store(regressor=regressor, name=name, inputs=inputs, outputfile=output_file)
    return regressor


if __name__=='__main__':
    import optparse
    usage = 'usage: python %prog [options]'
    parser = optparse.OptionParser(usage)
    parser.add_option('--inputfile', dest='input_file', help='Input file', default='tree.root')
    parser.add_option('--tree', dest='tree_name', help='Tree in the input file', default='tree')
    parser.add_option('--inputs', dest='inputs', help='List of input variables of the form "var1,var2,..."', default='x,y')
    parser.add_option('--target', dest='target', help='Target variable', default='target')
    parser.add_option('--eff', dest='eff', help='Efficiency working point', type='float', default=0.9)
    parser.add_option('--outputfile', dest='output_file', help='Output file', default='results.root')
    parser.add_option('--name', dest='name', help='Name used to store the regression results in the output file', default='regression')
    parser.add_option('--test', action="store_true", dest='test', help='Flag to test regression on a test sample', default=False)
    (opt, args) = parser.parse_args()
    #input_file = '/data_CMS/cms/sauvan/L1/2016/IsolationValidation/ZElectron/v_3_2016-06-23/tagAndProbe_isolationValidation_2016B_ZElectron.root'
    #tree_name = 'ntTagAndProbe_IsolationValidation_Stage2_Rebuilt_tree'
    #inputs = ['abs(ieta)', 'rho']
    #target = 'iso'
    inputs = opt.inputs.replace(' ','').split(',')
    main(inputfile=opt.input_file, tree=opt.tree_name, inputs=inputs, target=opt.target, outputfile=opt.output_file, name=opt.name, eff=opt.eff, test=opt.test)









