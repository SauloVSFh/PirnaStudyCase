'''
Module to access the API's from INOWAS and Pegel
'''

import requests
import sqlalchemy
import pandas as pd
from datetime import datetime
import numpy as np
import utils as u
import queries as q



def GetDivers (connection : sqlalchemy.engine.base.Connection):
    '''
    
    Parameters
    ----------
    connection : sqlalchemy.engine.base.Connection
        DESCRIPTION.

    Returns
    -------
    SensorsAPI_df : pandas.core.frame.DataFrame
        Retrieves the sensors from INOWAS.
    Sensors_df : pandas.core.frame.DataFrame
        Retrieves the combination of sensors and parameters according to what's stored in the database
    '''

    request = requests.get('https://sensors.inowas.com/list').json()
    request_index = [ i for i in request if i['project'] == 'DEU1']
    SensorsAPI_df = pd.DataFrame(request_index)
 
    
    #INDEX PARAMETERS FROM DATABASE INSTEAD. LEAVE THERE ONLY PARAMETERS OF INTEREST THAT WILL BE ADDED        
    parameters_query = 'select * from Variables'
    parameters_db = pd.read_sql(parameters_query, con = connection)
    
    Sensors_df = pd.DataFrame()
    for i in SensorsAPI_df.iterrows():
        row = i[1]

        params = row['parameters']
        params = [i for i in params if i in parameters_db.Name.values]
        name = row['name']
        df_ = pd.DataFrame({'Name' : params, 'Diver' : name})
        Sensors_df = pd.concat([Sensors_df,df_])
    Sensors_df = Sensors_df.reset_index(drop = True)
    Sensors_df = pd.merge(Sensors_df, parameters_db[['ID', 'Name']], on = 'Name')
    Sensors_df.columns = ['VariableName', 'Diver', 'VariableID']
    
    return SensorsAPI_df, Sensors_df


class Inowas (q.Get):
    
    def __init__(self, Get_, sensor, parameter : str, sts : int, ets : int):
        # Long url, short request -> one sensor one parameter
        ones1p_url = f'https://sensors.inowas.com/sensors/project/DEU1/sensor/{sensor}/parameter/{parameter}?timeResolution=RAW&dateFormat=epoch&start={sts}&end={ets}&gt=-100.0'
        
        
        '''
        long -> since a given date. This does not work well and only retrieve data from the last month.
        '''
        self.connection = Get_.connection
        
        self.ones1p_url = ones1p_url
        self.parameter = parameter
        self.sensor = sensor
        self.Get_ = Get_
        
    def Request(self):
        
        r = requests.get(self.ones1p_url).json()
        df = pd.DataFrame(r)
                       
        try :
            
            df.columns = ['TimeStamp', 'Value']
                            
            DiverData = self.Get_.DiverData(self.sensor)
    
            df ['MonitoringPointID'] = DiverData['MonitoringPointID'].iloc[0]
            
            df ['VariableID'] = self.Get_.VariableID(self.parameter)
            
            df = df [['MonitoringPointID','TimeStamp', 'VariableID', 'Value']]
            
            ReferenceAltitude = DiverData.ReferenceAltitude.iloc [0]
            DiverDepth = DiverData.DiverDepth.iloc [0]
        
            if self.parameter == 'h_level':
                head = ReferenceAltitude - DiverDepth + df.Value
                df = df.drop('Value', axis=1)
                df['Value'] = head
                
            self.Request_df = df
        
        except Exception:
            print('\nNo data retrieved')
            self.Request_df = None



class PegelAlarm (q.Get):

    def __init__ (self, Get_):
        
        #import instance variables to this class
        self.connection = Get_.connection
        self.Get_ = Get_
        
        self.GageData = Get_.MonitoringPointData(GageData = 1)
                       
        GageID = self.GageData.MonitoringPointID.iloc[0]
        
        t0, ts0 = Get_.APIDate (MonitoringPointID = GageID)
        
        t0 = u.TimeToString(t0)
        t1 = u.TimeToString(pd.to_datetime(datetime.now()).round('s'))
        
        parameter = f'&loadStartDate={t0}%2B0200&loadEndDate={t1}%2B0200'
        url = f'https://api.pegelalarm.at/api/station/1.0/a/saulo_filho_tudresden/height/501040-de/history?granularity=hour&{parameter}'
        
        self.url = url

    def Request(self):
        #get data from API and return a data frame
        r = requests.get(self.url)
        data_dict = r.json()['payload']['history']
        df = pd.DataFrame(data_dict)
        df.sourceDate = df.sourceDate.str.split('+', expand = True)[0]
        df['Time'] = pd.to_datetime(df['sourceDate'], dayfirst = True)
        df.columns = ['Value' , 0, 'Time']
        
        df['TimeStamp'] = np.round(df.Time.astype('int64') / 1e9)
        df ['VariableID'] = self.Get_.VariableID(var = 'Rh')
        df ['MonitoringPointID'] = self.GageData.MonitoringPointID.iloc[0]
        
        df = df [['MonitoringPointID','TimeStamp', 'VariableID', 'Value']]
        
        river_head = self.GageData.ReferenceAltitude.iloc[0] + df.Value / 100 #convert from cm to m
        df['Value'] = river_head
        
        self.Request_df = df





            
if __name__ == '__main__':
    
    path = 'D:\\Repos\\PirnaCaseStudy\\Data'
    database_fn = 'Database.db'
    database_fn = path + '\\' + database_fn

    Get = q.Get(database_fn)
    
    # r = PegelAlarm(Get)
    # r.Request()
    # df, update_id = u.Process(r.Request_df, Get)
    
    # print(r.MonitoringPointData())
    # print(r.GageData.columns)
    
    # I = Inowas(Get, 'I-2', 'ph', 1638445200, 1668465200 )
    # I.Request()
    a, sensors_df = GetDivers(Get.connection)