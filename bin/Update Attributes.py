#..............................................................................................................................
# Creator - Seth Docherty
# Date - 08/07/2015
# Purpose - Update feature class attributes from a source feature class. The source feature class is considered the "Master" and
#           the feature class that is going to be updated is the target.
#
#           The scripts user input requirements:
#               - Source FC (Master)
#               - Target FC (FC with attributes that need to be updated)
#               - Figure extent FC (FC that stores all the figures as objects)
#               - Figure Key Field (this is the field that stores the names of all the figure extent object. This field is
#                 required to be in the Target FC and spelled the same.
#               - Source Key Field (This is the field that will be used for joining data to the Target FC)
#               - Target Key Field (This is the field that will be used for joining data from the Source FC)
#               - Fields to update (User selects fields in the Target FC that need to be updated.  This field is
#                 required to be in the Target FC and spelled the same.)
#               - Figures to update (User selects figures that will be updated)
#
#           The script has built in error checking to make sure:
#               - Figure Key Field Exists
#               - Check to see if Target FC has GIS features for given figure. If does not exists, skips to next figure.
#
#           The script performs a simple if conditional check comparing the attributes in the Target FC against the Source FC.  If
#           the attributes are not the same, Target FC updates to match the Source FC attributes.
#
# Log:
#
#..............................................................................................................................

# Import arcpy module
import arcpy, os, operator, re, sys
from os.path import split, join
from datetime import datetime
from string import replace
arcpy.env.overwriteOutput = True

startTime = datetime.now()
print startTime

#Pull out recrods and make lists. Final List that is returned to variable
def get_geodatabase_path(input_table):
  '''Return the Geodatabase path from the input table or feature class.
  :param input_table: path to the input table or feature class
  '''
  workspace = os.path.dirname(input_table)
  if [any(ext) for ext in ('.gdb', '.mdb', '.sde') if ext in os.path.splitext(workspace)]:
    return workspace
  else:
    return os.path.dirname(workspace)

def ListRecords(fc,fields):
    records=[]
    with arcpy.da.SearchCursor(fc,fields) as cursor:
        for row in cursor:
            records.append(row)
        FigureHolder=[]
        for FigureHolder in zip(*records):
            FigureHolder
    return FigureHolder

#Check if there is a filepath from the input layers. If not, pre-pend the path. Also extract the FC names.
def InputCheck(Input):
    if not split(Input)[0]:
        InputPath = arcpy.Describe(Input).catalogPath #join(arcpy.Describe(Input).catalogPath,arcpy.Describe(Input).name)
        InputName = arcpy.Describe(Input).name
    else:
        InputPath = Input
        InputName = arcpy.Describe(Input).name
    return InputPath, InputName

#Find out if a Feature Layer exists.
def FL_Exist(LayerName, FCPath, Expression):
    if arcpy.Exists(LayerName):
        arcpy.Delete_management(LayerName)
    try:
        return arcpy.MakeFeatureLayer_management(FCPath, LayerName, Expression, "")
    except:
        return arcpy.AddError(arcpy.GetMessages(2))

def FieldExist(FC,field):
    fc_check = arcpy.ListFields(FC, field)
    if len(fc_check) == 1:
      return True
    else:
      return False

def unique_values(table, field):
    with arcpy.da.SearchCursor(table, [field]) as cursor:
        return sorted({row[0] for row in cursor})

def start_edit_session(fc_to_edit):
    # Start an edit session. Must provide the worksapce.
    workspace = get_geodatabase_path(fc_to_edit)
    edit = arcpy.da.Editor(workspace)
    # Edit session is started without an undo/redo stack for versioned data and starting edit operation
    #  (for second argument, use False for unversioned data)
    edit.startEditing(False, False)
    edit.startOperation()

def stop_edit_session():
    edit.stopOperation()
    edit.stopEditing(True)

def Get_Figure_List(FCpath, Keyfield, User_Selected_Figures):
    FigureList=[]
    if User_Selected_Figures == "0":
        if arcpy.ListFields(FCpath,Keyfield,"String"): #Check if the field type of the of the Figure Extent Key field is a string or not.
            Figures = ListRecords(FCpath,Keyfield)
            FigureList = ["'" + item + "'" for item in Figures] #Adding single quotes at the beginning/end of each item.
            arcpy.AddMessage(str(len(FigureList)) + " Figures are going to be updated")
        else:
            FigureList = ListRecords(FCpath,Keyfield)
            arcpy.AddMessage(str(len(FigureList)) + " Figures are going to be updated")
    elif arcpy.ListFields(FCpath,Keyfield,"String"):  #Check if the field type of the of the Figure Extent Key field is a string or not.
        split = [item.strip("'") for item in User_Selected_Figures.split(";")] #List Comprehension which splits delimited string and removes any qoutes.
        FigureList = ["'" + item.strip() + "'" for item in split] #List Comprehension which adds single quotes at the beginning/end of each item in the List. The qoutes are added for ArcMap Definition query expressions.
        arcpy.AddMessage(str(len(FigureList)) + " Figure(s) are going to be updated")
    else:
        FigureList = [item.strip("'") for item in User_Selected_Figures.split(";")] #List Comprehension which splits delimited string and removes any qoutes that may be present in string.
        arcpy.AddMessage(str(len(FigureList)) + " Figure(s) are going to be updated")
    return FigureList

def Does_Figure_Exist(childFCpath, childFC, figure, child_figure_list, figure_key_field):
    print "Runtime: ", datetime.now()-startTime
    arcpy.AddMessage(40*'.' + '\n' + "Runtime: {}".format((datetime.now()-startTime)))
    print "Figure Name: {}" + str(figure)
    arcpy.AddMessage(40*'.' + "Updating Figure: {}".format(str(figure)))
    clause = ("{} = {}".format(figure_key_field,figure))

    # Check to see if figure name exists in sample location FC
    # If does not exists, skip to next figure.
    if figure not in child_figure_list:
        print ("{} is not in {}.  Skipping to next figure.".format(figure,childFC))
        arcpy.AddMessage(("{} is not in {}.  Skipping to next figure.".format(figure,childFC)))
        return False
    else:
        return clause

def update_field(Sourcepath, targetpath, SourceTableField, TargetTableField, field, clause=''):
    SourceFCpath, SourceFC = InputCheck(Sourcepath)
    targetFCpath, targetFC = InputCheck(targetpath)

    print "."*25 + "Updating the following field: " + field + " (" + str(datetime.now()-startTime)+")"
    arcpy.AddMessage("."*25 + "Updating the following field: " + field + " (" + str(datetime.now()-startTime)+")")
    Source_dict = dict([(r[0], (r[1])) for r in arcpy.da.SearchCursor(SourceFCpath, [SourceTableField,field])])
    Target_dict = dict([(r[0], (r[1])) for r in arcpy.da.SearchCursor(targetFCpath,[TargetTableField,field],clause)])
    updateRows = arcpy.da.UpdateCursor(targetFCpath,[TargetTableField,field],clause) #Cursor to be used to update attributes in project FC
    Source_dictSet = set(Source_dict)
    Target_dictSet = set(Target_dict)
    Source_dictUpdate = dict()
    for key in Source_dictSet.intersection(Target_dictSet):
        if key not in Source_dictUpdate:
            Source_dictUpdate[key] = dict()
        Source_dictUpdate[key] = Source_dict[key]
    ls = []
    record_check = [Source_dictUpdate[k] == v for k, v in Target_dict.iteritems() if k in Source_dictUpdate] #Getting a count of values that are not the same in A:value and B:value
    if record_check.count(False) == 0: #Count
        print ("There are no records to update in {}".format(field))
        arcpy.AddMessage(("There are no records to update in {}".format(field)))
    else:
        for updateRow in updateRows:
            source_join = updateRow
            if source_join[0] in Source_dictUpdate:
                if source_join[1] != Source_dictUpdate[source_join[0]]:
                    print ("Updating {} to {}".format(source_join[0], Source_dictUpdate[source_join[0]]))
                    arcpy.AddMessage(("Updating {} to {}".format(source_join[0], Source_dictUpdate[source_join[0]])))
                    updateRow[1] = Source_dictUpdate[source_join[0]]
            updateRows.updateRow(updateRow)
        del updateRow, updateRows

def Update_Figures(Report_Sample, MasterSample, FigureExtent, FigureExtent_KeyField, SourceTableField, TargetTableField, input_field, input_figures):
    MasterSamplepath, MasterSampleFC = InputCheck(MasterSample)
    Report_SampleFCpath, Report_SampleFC = InputCheck(Report_Sample)
    FigureExtentpath, FigureExtentFC = InputCheck(FigureExtent)

    start_edit_session(Report_SampleFCpath)

    if input_figures == "None":
        #Formatting the input fields to be updated
        Field_to_update = input_field.split(";")
        arcpy.AddMessage("The following fields are going to be updated: {}".format(str(Field_to_update)))
        for field in Field_to_update:
            if (not FieldExist(MasterSamplepath,field)):
                arcpy.AddMessage(("{} is not in {}.  Skipping to next field.".format(field,MasterSampleFC)))
            else:
                update_field(MasterSamplepath, Report_SampleFCpath, SourceTableField, TargetTableField, field)
    else:
       #Check to see if all the Report feature classes have the FigureExtent Keyfield.
        if not (FieldExist(Report_SampleFCpath,FigureExtent_KeyField)):
            arcpy.AddError(("The field {} does not exist in {}".format(FigureExtent_KeyField,Report_SampleFC)))
            sys.exit()
   
        # Getting List of values to update.  List is based on values from Figure Extent
        FigureList = Get_Figure_List(FigureExtentpath, FigureExtent_KeyField, input_figures)
    
        #Get list of figures in the report FC
        ReportFC_FigureList = unique_values(Report_SampleFCpath,figure_key_field)
        ReportFC_FigureList = ["'" + item + "'" for item in ReportFC_FigureList]

        #Formatting the input fields to be updated
        Field_to_update = input_field.split(";")
        arcpy.AddMessage("The following fields are going to be updated: {}".format(str(Field_to_update)))

        #Loop through all figures and update Project Feature Class
        for figure in FigureList:
            clause = Does_Figure_Exist(Report_SampleFCpath, Report_SampleFC, figure, ReportFC_FigureList, figure_key_field)
            if clause:
                for field in Field_to_update:
                    if (not FieldExist(MasterSamplepath,field)):
                      arcpy.AddMessage(("{} is not in {}.  Skipping to next field.".format(field,MasterSampleFC)))
                    else:
                        update_field(MasterSamplepath, Report_SampleFCpath, SourceTableField, TargetTableField, field, clause)
     
    stop_edit_session()
           
try:

    MasterSample = arcpy.GetParameterAsText(0)
    Report_Sample = arcpy.GetParameterAsText(1)
    FigureExtent = arcpy.GetParameterAsText(2)
    FigureExtent_KeyField = arcpy.GetParameterAsText(3)
    SourceTableField = arcpy.GetParameterAsText(4) #The Master Feature Class
    TargetTableField = arcpy.GetParameterAsText(5) #The Project Feature Class
    input_field = arcpy.GetParameterAsText(6)
    input_figures = arcpy.GetParameterAsText(7)

    Update_Figures(Report_Sample, MasterSample, FigureExtent, FigureExtent_KeyField, SourceTableField, TargetTableField, input_field, input_figures)

    print "Script Runtime: ", datetime.now()-startTime
    arcpy.AddMessage("Script Runtime: " + str(datetime.now()-startTime))

except Exception, e:
    # If an error occurred, print line number and error message
    import traceback, sys
    tb = sys.exc_info()[2]
    arcpy.AddError("Line %i" % tb.tb_lineno)
    arcpy.AddError(e.message)
    print "Line %i" % tb.tb_lineno
    print e.message