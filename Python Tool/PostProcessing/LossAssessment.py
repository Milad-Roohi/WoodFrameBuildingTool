# Import packages
import numpy as np
import math
import os
import pandas as pd
import sqlite3
import random

from scipy.stats import lognorm
from scipy.stats import binom
from scipy.stats import norm
from scipy.stats import truncnorm
from scipy.stats import uniform
from scipy.optimize import minimize
from scipy import interpolate

from Component import component # Predefined component class
import random
np.random.seed(1000)


def sampledist(DistributionName, Mean, Std):
    # This function is used for generate random variable (loss and downtime) given distribution of the variable
    if DistributionName == 'Normal':
        temp = norm.rvs(loc=Mean, scale=Std, size=1, random_state=None)
        return temp[0]
#     else: return np.exp(norm.rvs(loc=np.log(Mean), scale=Std, size=1, random_state=None))
    elif DistributionName == 'LogNormal':
        p = np.poly1d([1,-1,0,0, -(Std/Mean)**2])
        r = p.roots
        sol = r[(r.imag == 0)&(r.real >0)].real
        shape = np.sqrt(np.log(sol))
        scale = Mean * sol
        
        return lognorm.rvs(shape,0, scale, size = 1)[0]
#     else: return np.random.lognormal(np.exp(Mean), np.exp(Std), 1)

conn = sqlite3.connect('component.db')
conn.commit()

c = conn.cursor()
def get_components_by_id(id):
    c.execute ("SELECT * FROM component WHERE ID =:ID",{'ID': id})
    return c.fetchone()


def ComponentLoss (ComponentID, EDP, Quantity):
    # This function is used for computing the expected loss of one kind of component in a story given EDP
    # All structural, non-structural and equipment will be contained in this part
    # For components whose 'Directional' is 'Yes', 2 directions quantities and EDPs should be considered saperately and sum them up
    ##############################################################################################################################################
    # Input:
    # ComponentID      The component currently considered, which should be incorperate with FEMA P-58 database. Refer the attached spreadsheet 
    #                  for more information. In string format.                    
    # EDP              Engineering demand parameter, either SDR of PFA, which should be corresponding to component demand parameter. One number           
    # Quantity         Quantity of considered component in currenty story  
    ##############################################################################################################################################
    # Composition of class 'component': 
    #(ID, Name, Description, DMP, NumDS, DSHierarchy, Unit, Measure, DSProb, EDPMean, EDPStd, Directional,
    # LossDist, LossStd, LossLowQty, LossLowMean, LossUpQty, LossUpMean, DTDist, DTStd, DTLowQty, DTLowMean, DTUpQty, DTUpMean, CostScalar)
    ##############################################################################################################################################
    
    temp = get_components_by_id(ComponentID)
    NumDS = int(temp[4])
    # Define the component class 
    c1 = component(temp[0], temp[1], temp[2], temp[3], temp[4], temp[5], temp[6], temp[7], temp[8:8+NumDS], temp[13:13+NumDS], temp[18:18+NumDS], temp[23],\
                               temp[24:24+NumDS], temp[29:29+NumDS], temp[34:34+NumDS], temp[39:39+NumDS], temp[44:44+NumDS], temp[49:49+NumDS], temp[54:54+NumDS], temp[59:59+NumDS], temp[64:64+NumDS], temp[69:69+NumDS], temp[74:74+NumDS], \
                               temp[79:79+NumDS], temp[84])

    # Uniformly generate probability from 0 to 1 and determine which damage state the random variable is currently in 
#     Pr = uniform.rvs(loc=0, scale=1, size=1, random_state=None)
    Pr = uniform.rvs(size=1)
    Prob_DS = []
    I_DS = []
    ActualLoss_DS = []
    ActualDT_DS = []

    for i in range(c1.NumDS):
        # Prob_DS is used for storing the probability in each damage state given EDP
        Prob_DS.append(norm.cdf(np.log(EDP), loc = np.log(c1.EDPMean[i]), scale = c1.EDPStd[i])) 
    Prob_DS = np.insert(Prob_DS,0,1)

        # I_DS is the indicator list for storing binary indicator whether the uniformly generated probability in current damage state or not
    for i in range(1,c1.NumDS+1):
        if Pr <= Prob_DS[i-1] and Pr >= Prob_DS[i]:
            I_DS.append(1)            
        else: I_DS.append(0)
            
    if Pr <= Prob_DS[-1]:
        I_DS.append(1)
    else: I_DS.append(0)
        
    EDPMeantemp = np.insert(c1.EDPMean,0,0)
    for i in range(c1.NumDS):
        if EDPMeantemp[i] == EDPMeantemp[i+1]:
            I_DS[i] = I_DS[i+1]
        else: I_DS[i] = I_DS[i]

    ActualLoss_DS.append(0)
    ActualDT_DS.append(0)
    
    for i in range(1,c1.NumDS+1):

        # Use linear interpolation to find the mean loss corresponding to the quantity of current considered component 
        MeanLoss_DS = np.interp(Quantity,[c1.LossLowQty[i-1],c1.LossUpQty[i-1]], [c1.LossLowMean[i-1],c1.LossUpMean[i-1]])

        # Randomly sample loss for current damage state of current considered component 
        SampleLoss = sampledist(c1.LossDist[i-1], MeanLoss_DS, c1.LossStd[i-1]*MeanLoss_DS)

        # Actual loss for current realization = sampled loss x proportion of damage states contribution x quantity of current component x whether current realization in current damage state
        ActualLoss_DS.append(SampleLoss*c1.DSProb[i-1]*Quantity*I_DS[i])

        # Use linear interpolation to find the mean downtime corresponding to the quantity of current considered component 
        MeanDT_DS = np.interp(Quantity,[c1.DTLowQty[i-1],c1.DTUpQty[i-1]], [c1.DTLowMean[i-1],c1.DTUpMean[i-1]])

        # Randomly sample downtime for current damage state of current considered component 
        SampleDT = sampledist(c1.DTDist[i-1], MeanDT_DS, c1.DTStd[i-1]*MeanDT_DS)

        # Actual downtime for current realization = sampled loss x proportion of damage states contribution x quantity of current component x whether current realization in current damage state
        ActualDT_DS.append(SampleDT*c1.DSProb[i-1]*Quantity*I_DS[i])
        
    return np.sum(ActualLoss_DS)



def SampleEDP(aggregatedEDP, beta, NumRealizations):
    # This function is used for randomly sampling engineering demand parameters used for loss assessment
    ##############################################################################################################################################
    # Input:
    # aggregatedEDP      Aggregated EDPs at one intensity level, including SDR, PFA and RDR, attention: this function takes the original EDPs from the analsis
    # beta               Uncertainties, first row is model uncertainty, second row is ground motion uncertainty         
    # NumRealizations    Number of simulations at current intensity level
    # Output:
    # W                  Random sampled EDPs, including both collapse and non-collapse EDPs
    ##############################################################################################################################################
     
    EDPs = aggregatedEDP
    # ln scale of the input EDP
    lnEDPs = np.log(EDPs)

    # Number of rows
    num_rec = EDPs.shape[0]
    # Number of columns 
    num_var = EDPs.shape[1]

    lnEDPs_mean = np.array(np.mean(lnEDPs, axis = 0).T)
    lnEDPs_cov = np.cov(lnEDPs.T)

    lnEDPs_cov_rank = np.linalg.matrix_rank(lnEDPs_cov)

    # pay attention to the data format here, it has to be a column vector
    sigma = np.array(np.sqrt(np.diag(lnEDPs_cov))).reshape([num_var,1]) 
    sigmap2 = sigma * sigma

    R = lnEDPs_cov / (np.matmul(sigma,sigma.T))

    B = np.array(beta).reshape([1,2])

    # Incorporate with uncertainties
    sigmap2 = sigmap2 + B[:,0] * B[:,0]
    sigmap2 = sigmap2 + B[:,1] * B[:,1]
    sigma = np.sqrt(sigmap2)
    sigma2 = np.matmul(sigma , sigma.T) 
    lnEDPs_cov_inflated = R * sigma2


    D2_total,L_total = np.linalg.eig(lnEDPs_cov_inflated)

    idx = D2_total.argsort()  
    D2_total = D2_total[idx]
    L_total = L_total[:,idx]


    if lnEDPs_cov_rank >= num_var:
        L_use = L_total
    else:
        L_use = L_total[:, num_var - lnEDPs_covrank + 1 : num_var] # still have to check this part

    if lnEDPs_cov_rank >= num_var:
        D2_use = D2_total
    else: D2_use = D2_total[num_var - lnEDPs-cov_rank + 1: num_var] # still have to check this part

    D_use =np.diagflat(np.sqrt(D2_use))

    if lnEDPs_cov_rank >= num_var:
        U = np.random.randn(NumRealizations*num_var).reshape([num_var, NumRealizations])
    else: U = np.random.randn(NumRealizations, lnEDPs_cov_rank).reshape([num_var, NumRealizations])

    Lambda = -np.matmul(L_use , D_use)

    Z = np.matmul(Lambda , U) + np.repeat(lnEDPs_mean.reshape([num_var,1]), NumRealizations, axis=1)

    lnEDPs_sim_mean = np.mean(Z.T, axis = 0)
    lnEDPs_sim_cov = np.cov(Z)

    A = lnEDPs_sim_mean/lnEDPs_mean.T  #Table G-7, or Table G-16
    B = lnEDPs_sim_cov/lnEDPs_cov  #Table G-8, or Table G-17
    W = np.exp(Z)
    sampledEDP = pd.DataFrame(W.T,columns = aggregatedEDP.columns)
    return W


def performLossAssessment(ComponentList, NumStory, CollapseCriteria, SDRTotal, PFATotal, RDRTotal, theta_collapse, HazardData, BuildingValue, beta, NumSimulations, DemolitionSW):

# This function is used for randomly sampling engineering demand parameters used for loss assessment
##############################################################################################################################################
# Input:
# ComponentList  DataFrame  With column ['Story Number','ID','Direction','Quantity','ResponseType','ComponentType']
# NumStory       int        Number of stories in loss model
# SDRTotal       DataFrame  Total maximum story drift ratio directly extract from NRHA, with SP3 form. WITH COLLAPSE DATA!
# PFATotal       DataFrame  Total maximum peak floor acceleration directly extract from NRHA, with SP3 form. WITH COLLAPSE DATA!
# RDRTotal       DataFrame  Total maximum residual drift ratio directly extract from NRHA, with SP3 form. WITH COLLAPSE DATA!
# theta_collapse list       Collapse median and disperion, probability of collapse is given by norm.cdf(np.log(IM), loc = np.log(theta[0]), scale = theta[1])
# HazardData     DataFrame  Hazard information used for NRHA, the first column is intensity measure, the second column is annual probability of exceedance
# BuildingValue  int        Total square footage x price per square footage
# beta           array      2 rows numpy array, the first row is model uncertainty, the second row is GM uncertainty
# NumSimulations int        Number of engineering demand parameters simulations in each hazard level
# DemolitionSW   bool       Whether extra 25% of demolition cost is considered. If turning on, the total collapse cose would be 125% of building value.
# Output:
# Loss           DataFrame  ('HazardLevel', 'CollapseLoss', 'DemolitionLoss','ComponentLoss')
##############################################################################################################################################
    
    CLoss = [] # Collapse Losses List
    DLoss = [] # Demolition Losses List
    ComLoss = [] # Structural Components' Losses List
    
    NumHazardLevel = HazardData.shape[0] # Number of hazard levels in analysis
    

    for i in range(1,NumHazardLevel+1):

        SDRX = SDRTotal[(SDRTotal.loc[:,0] == i) & (SDRTotal.loc[:,1] == 1)]
        PFAX = PFATotal[(PFATotal.loc[:,0] == i) & (PFATotal.loc[:,1] == 1)]
        RDRX = RDRTotal[(RDRTotal.loc[:,0] == i) & (RDRTotal.loc[:,1] == 1)]

        SDRZ = SDRTotal[(SDRTotal.loc[:,0] == i) & (SDRTotal.loc[:,1] == 2)]
        PFAZ = PFATotal[(PFATotal.loc[:,0] == i) & (PFATotal.loc[:,1] == 2)]
        RDRZ = RDRTotal[(RDRTotal.loc[:,0] == i) & (RDRTotal.loc[:,1] == 2)]

        # Prepare the EDPs at current intensity level and sample EDPs
        SDRX_pure = SDRX.loc[:,3:SDRX.shape[1]]
        PFAX_pure = PFAX.loc[:,3:PFAX.shape[1]]
        RDRX_pure = RDRX.loc[:,3:RDRX.shape[1]]

        AggregatedEDPs = pd.concat([SDRX_pure, PFAX_pure,RDRX_pure], axis=1)
        sampledEDPXs = SampleEDP(AggregatedEDPs, beta, NumSimulations)

        Cur_SDRX = sampledEDPXs[0:NumStory]
        Cur_PFAX = sampledEDPXs[NumStory:NumStory+NumStory+1]
        Cur_RDRX = sampledEDPXs[-1]

        SDRZ_pure = SDRZ.loc[:,3:SDRZ.shape[1]]
        PFAZ_pure = PFAZ.loc[:,3:PFAZ.shape[1]]
        RDRZ_pure = RDRZ.loc[:,3:RDRZ.shape[1]]

        AggregatedEDPs = pd.concat([SDRZ_pure, PFAZ_pure, RDRZ_pure], axis=1)
        sampledEDPZs = SampleEDP(AggregatedEDPs, beta, NumSimulations)

        Cur_SDRZ = sampledEDPZs[0:NumStory]
        Cur_PFAZ = sampledEDPZs[NumStory:NumStory+NumStory+1]
        Cur_RDRZ = sampledEDPZs[-1]

        # Initialize 
        tempCLoss = [] # used for recording all the collapse losses in the ith hazard level
        tempDLoss = [] # used for recording all the demolition losses in the ith hazard level   
        tempComLossTotal = [] # used for recording all the component losses in the ith hazard level

        IM = HazardData.iloc[i-1,0]
        
        # Compute collapse losses
        if DemolitionSW == 'true':
            totalLossRatio = 1.25
        else: totalLossRatio = 1.00
            
        Prob_Collapse = norm.cdf(np.log(IM), loc = np.log(theta_collapse[0]), scale = theta_collapse[1])

        CLoss.append(totalLossRatio * Prob_Collapse)

        Prob_NonCollapse = 1 - Prob_Collapse

        # Input EDPs for SP3 method are from randomly generated non-collapse EDPs 
        for k in range(NumSimulations):

            MaxSDR = max(max(sampledEDPXs[0:NumStory][:,k]),max(sampledEDPZs[0:NumStory][:,k]))
            MaxRDR = max(Cur_RDRX[k],Cur_RDRZ[k])

            if MaxSDR >= CollapseCriteria: # When collapse happens, no demolition and component loss
                continue
                
            else: 
                if MaxRDR > 0.01: #If non-collapse, judge whether domolition happens based on max residual drift
                    tempDLoss.append(totalLossRatio)
                    tempComLossTotal.append(0)
                    continue

                else: 

                    tempDLoss.append(0) # If non-collapse & non-demolition, compute component losses
                    tempCom = []

                    # loop over all components in component list
                for j in range(ComponentList.shape[0]):

                    if ComponentList.iloc[j,4] == 'SDR':

                        if ComponentList.iloc[j,2] == 'None': # Non directional components
                            # 1.2 times the Maximum SDR of the two directions
                            BiSDR = 1.2*(max(Cur_SDRX[ComponentList.iloc[j,0]-1][k], Cur_SDRZ[ComponentList.iloc[j,0]-1][k]))
                            tempCom.append(ComponentLoss(ComponentList.iloc[j,1], BiSDR, float(ComponentList.iloc[j,3])))

                        else: 
                            if ComponentList.iloc[j,0] == 1:
                                tempCom.append(ComponentLoss(ComponentList.iloc[j,1], Cur_SDRX[int(ComponentList.iloc[j,0])-1][k], float(ComponentList.iloc[j,3])))
                            else: 
                                tempCom.append(ComponentLoss(ComponentList.iloc[j,1], Cur_SDRZ[int(ComponentList.iloc[j,0])-1][k], float(ComponentList.iloc[j,3])))

                    else:
                        if ComponentList.iloc[j,2] == 'None': # Non directional components
                            # 1.2 times the Maixmum PFA of the two directions
                            BiPFA = 1.2*(max(Cur_PFAX[int(ComponentList.iloc[j,0])][k], Cur_PFAZ[int(ComponentList.iloc[j,0])][k]))
                            tempCom.append(ComponentLoss(ComponentList.iloc[j,1],BiPFA, float(ComponentList.iloc[j,3])))

                        else:
                            if ComponentList.iloc[j,0] == 1:
                                tempCom.append(ComponentLoss(ComponentList.iloc[j,1], Cur_PFAX[int(ComponentList.iloc[j,2])][k], float(ComponentList.iloc[j,3])))
                            else:
                                tempCom.append(ComponentLoss(ComponentList.iloc[j,1], Cur_PFAZ[int(ComponentList.iloc[j,2])][k], float(ComponentList.iloc[j,3])))

                tempComLossTotal.append(np.sum(tempCom))

        DLoss.append(np.mean(tempDLoss) * Prob_NonCollapse)
        ComLoss.append(np.mean(tempComLossTotal)/BuildingValue * Prob_NonCollapse)
        
#         DLoss.append(np.mean(tempDLoss) )
#         ComLoss.append(np.mean(tempComLossTotal)/BuildingValue )
        
    print(len(ComLoss))
    Loss = pd.DataFrame(
    {'HazardLevel': HazardData.iloc[:,0],
     'CollapseLoss': CLoss,
     'DemolitionLoss': DLoss,
     'ComponentLoss': ComLoss
    })
    
    return Loss

columns = ['Story Number','ID','Direction','Quantity','ResponseType','ComponentType']
index = range(0,1)
ComponentList = pd.DataFrame(index=index, columns=columns)
ComponentList.loc[0,:] = [2,'B1071.011',1,7.2,'SDR','Structural']
ComponentList.loc[1,:] = [2,'B1071.011',2,5.4,'SDR','Structural']
ComponentList.loc[2,:] = [1,'B1071.011',1,1.6,'SDR','Structural']
ComponentList.loc[3,:] = [1,'B1071.011',2,1.2,'SDR','Structural']
ComponentList.loc[4,:] = [2,'C1011.011a',1,0.8,'SDR','Structural']
ComponentList.loc[5,:] = [2,'C3011.001a',1,0.14,'SDR','Structural']
ComponentList.loc[6,:] = [2,'C3011.002a',1,0.14,'SDR','Structural']
ComponentList.loc[7,:] = [2,'C1011.011a',2,0.62,'SDR','Structural']
ComponentList.loc[8,:] = [2,'C3011.001a',2,0.11,'SDR','Structural']
ComponentList.loc[9,:] = [2,'C3011.002a',2,0.11,'SDR','Structural']

NumStory = 2
beta = np.array([0,0]).reshape([2,1])

HazardData = pd.DataFrame(data = [0.177852,0.273467,0.444298,0.5601,0.65216,0.790259,0.982082,1.246203,1.563623, 2.013842])
BuildingValue = 200 * 30 * 40 * 2


seed = int(os.getenv('SGE_TASK_ID'))
for i in range(seed, seed+1):
    os.chdir('LHS/case%d'%i)
    SDR = pd.read_csv('SDR.csv', header = None)
    PFA = pd.read_csv('PFA.csv', header = None)
    RDR = pd.read_csv('RDR.csv', header = None)
    theta_collapse = np.loadtxt("CollapseFragility.csv", delimiter=",")
    Loss = performLossAssessment(ComponentList, NumStory, 0.2, SDR, PFA, RDR, theta_collapse, HazardData, BuildingValue, beta, 10000, 'false')
#     os.chdir('/Users/rover/Desktop/Results')
#     os.mkdir('case%d'%i)
#     os.chdir('case%d'%i)
    Loss.to_csv('Loss.csv')



