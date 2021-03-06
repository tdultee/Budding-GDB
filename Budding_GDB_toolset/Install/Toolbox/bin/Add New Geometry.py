#..............................................................................................................................
# Creator - Seth Docherty  Test
# Purpose - Figure creator for SMSR Report.  Updates figures with new locations which are used for field status maps.
#
# Log:
#	1. Complete overhaul of code. 08/12/2016
#   
# TODO:
#   1. Add a check to look for geometry  that are stacked on top of each other. 3/31/2015
#        - Compares the number of records in the output "Locations in secondary output" and the report FC.
#        - If the number of records are the same, continue with script
#        - If the number of records are not the same, will need to create a list of locations that are not in the report FC.
#        - The additional records will be added to the Feature_Check_Selection which is the Sample_Check FC.
#
#..............................................................................................................................

# Import arcpy module
import os, arcpy, sys
from datetime import datetime
from os.path import split, join
from helper import *
arcpy.env.overwriteOutput = True

startTime = datetime.now()
print startTime

try:

    #..............................................................................................................................
    #User Input data
    #..............................................................................................................................

    #Sitewide Sample Location from Chevron GDB
    Parent = arcpy.GetParameterAsText(0)

    #File path for the Report Sample locatcion Feature Class
    Child = arcpy.GetParameterAsText(1)

    #The Boundary extent that is associated with the Figure.
    Secondary_Boundary = arcpy.GetParameterAsText(2)

    #Figure Extent FC
    FigureExtent = arcpy.GetParameterAsText(3)

    #The location boundary that is associated with the Figure Extent.
    FigureExtent_KeyField = arcpy.GetParameterAsText(4)

    #SQL Expression to type in the figures that need to be updated.	If all figures need to be updated, please type in '0'.
    input_figures = arcpy.GetParameterAsText(5)

    #Field that will be used to expression to delete necessary samples.  Please specify a field even if no values need to be deleted.
    Delete_Field = arcpy.GetParameterAsText(6)

    #SQL Expression: Select values that need to be delted. Separate each value with a ;.  If no values need to be deleted, please type in '0'.
    What_To_Delete_List = arcpy.GetParameterAsText(7)

    #Input Feature Dataset in Scratch GDB
    Input_ScratchFD = arcpy.GetParameterAsText(8)

    #..............................................................................................................................
    #Hard Coded Data
    #..............................................................................................................................

    #Check if there is a filepath from the input layers. If not, pre-pend the path. Also extract the FC names.
    ParentPath, ParentFC = InputCheck(Parent)
    ChildPath, ChildFC = InputCheck(Child)
    FigureExtentpath, FigureExtentFC = InputCheck(FigureExtent)

    if Secondary_Boundary:
        SecondaryBoundarypath, SecondaryBoundaryFC = InputCheck(Secondary_Boundary)
    else:
        SecondaryBoundarypath, SecondaryBoundaryFC = InputCheck(FigureExtent)

    #Check to see if all the Report feature classes have the FigureExtent Keyfield.
    if not all((FieldExist(ChildPath,FigureExtent_KeyField), FieldExist(FigureExtentpath,FigureExtent_KeyField), FieldExist(SecondaryBoundarypath,FigureExtent_KeyField))):
        arcpy.AddError(("The field {} does not exist in {}, {} or {}".format(FigureExtent_KeyField,ChildFC,FigureExtentFC,SecondaryBoundaryFC)))
        sys.exit()

    #Extracting File Paths for Feature Dataset and Scratch File Geodatabase
    Scratch_FDPath = join(arcpy.Describe(Input_ScratchFD).catalogPath,(Input_ScratchFD))
    Scratch_FD = Scratch_FDPath.rsplit("\\",1)[1]
    in_mem_path = "in_memory"

    #Setting the file path for the Temp FC's that will be created in the Scratch GDB.
    #In Memory Features
    FigSelection = Scratch_FD + "_FigureSelection"
    FigSelectionPath = os.path.join(in_mem_path,FigSelection)
    SpatialTmp = Scratch_FD + "_SpatialJoinTemp"
    SpatialTmpPath = os.path.join(in_mem_path,SpatialTmp)
    TempCheck = Scratch_FD + "_Point_CheckTmp"
    TempCheck_Path = os.path.join(in_mem_path,TempCheck)

    #Temporary features stored in the Scratch Database
    Figure_Extent_Selection = Scratch_FD + "_FigureExtent_Selection"
    Figure_Extent_Selection_Path = os.path.join(Scratch_FDPath,Figure_Extent_Selection)
    Secondary_Boundary_Selection = Scratch_FD + "_BoundaryExtent_Selection"
    Secondary_Boundary_Selection_Path = os.path.join(Scratch_FDPath,Secondary_Boundary_Selection)
    Feature_Check_Selection = Scratch_FD + "_FinalOutput"
    Feature_Check_Selection_Path = os.path.join(Scratch_FDPath,Feature_Check_Selection)

    #Create the 3 Main Features Class's that will be stored in the Scratch GDB
    FC_Exist(Figure_Extent_Selection, Scratch_FDPath, ChildPath)
    FC_Exist(Secondary_Boundary_Selection, Scratch_FDPath, ChildPath)
    FC_Exist(Feature_Check_Selection, Scratch_FDPath, ChildPath)

    #........................................................................................................................................
    #Setting up the Feature Class that stores the Figure Extent Polygons that will be updated.
    #........................................................................................................................................

    #Getting the number of figures to update
    FigureList = Get_Figure_List(FigureExtentpath, FigureExtent_KeyField, input_figures)
    arcpy.AddMessage("The following figure(s) are going to be updated:")
    for item in FigureList:
        arcpy.AddMessage(item)

    #Make Feature Layer from Figure Extent FC
    OutputLayer_FigureExtentFC = FigureExtentFC + "_Layer" #InputLayer + "_Layer"
    Create_FL(OutputLayer_FigureExtentFC,FigureExtentpath,"")

    #Selecting the records found the Figure list
    for value in FigureList:
        clause = buildWhereClause(OutputLayer_FigureExtentFC, FigureExtent_KeyField, value)
        arcpy.SelectLayerByAttribute_management(OutputLayer_FigureExtentFC,"ADD_TO_SELECTION", clause)

    #Copy all selected records to a standalone Feature Class which holds the all figure that will be updated.
    arcpy.CopyFeatures_management(OutputLayer_FigureExtentFC, FigSelectionPath)

    arcpy.Delete_management(OutputLayer_FigureExtentFC)
    arcpy.AddMessage("Successfully created the Features Class, {}, which contains the figures to be updated.".format(FigSelection))
    print "Successfully created the Features Class, {}, which contains the figures to be updated.".format(FigSelection)

    print "......................................................................Initial Setup Runtime: {} (Total Runtime: {})".format(datetime.now()-startTime, datetime.now()-startTime)
    arcpy.AddMessage("......................................................................Initial Setup Runtime: {} (Total Runtime: {})".format(datetime.now()-startTime, datetime.now()-startTime))


    #..............................................................................................................................
    # PART 1
    # Samples within Figure Extent - Part of the program that performs a spatial join of sample locations from the Source GDB and
    # the selected figures in the figure selection feature classes
    #..............................................................................................................................
    part1time = datetime.now()
    print "Part 1: Selecting all the features that fall within the figure extents and deleting user specified record values...\n...\n...\n..."
    arcpy.AddMessage("Part 1: Selecting all the features that fall within the figure extents and deleting user specified record values...\n...\n...\n...")

    arcpy.SpatialJoin_analysis(ParentPath,FigSelectionPath,SpatialTmpPath,"JOIN_ONE_TO_MANY","KEEP_ALL","","INTERSECT", "", "" )
    Select_and_Append(FigSelectionPath, SpatialTmpPath, Figure_Extent_Selection_Path)

    #...................................................................................................................................
    # Delete Samples - Part of the program that goes through Figure Extent Selection FC and deletes user specified samples types.
    #...................................................................................................................................

    Delete_Values_From_FC(What_To_Delete_List, Delete_Field, Figure_Extent_Selection, Figure_Extent_Selection_Path)

    print "......................................................................Part 1 Runtime: {} (Total Runtime: {})".format(datetime.now()-part1time, datetime.now()-startTime)
    arcpy.AddMessage("......................................................................Part 1 Runtime: {} (Total Runtime: {})".format(datetime.now()-part1time, datetime.now()-startTime))

    #.....................................................................................................................................................
    # PART 2
    # Part of the program that goes through the features within the Figure Extent (Figure_Extent_Selection_Path)
    # and extracts all the features that fall inside a secondary boundary e.g. group location boundary, in each figure and saves to a standalone feature class.
    # This part of the program basically creates a sub-selection of features that fall inside the figure extent. e.g. 10 features fall inside
    # figure extent but out of that 10, 5 fall in the boundary exent. If there is no boundary exent, just select the Figure Extent Feature Class.
    #.....................................................................................................................................................
    part2time = datetime.now()
    print "Part 2: Selecting the features within each figure extent that fall within the secondary boundary...\n...\n...\n..."
    arcpy.AddMessage("Part 2: Selecting the features within each figure extent that fall within the secondary boundary...\n...\n...\n...")

    for value in FigureList:
        arcpy.AddMessage("Working on figure...................." + str(value))
        print "Working on figure...................." + str(value)
        clause = buildWhereClause(Figure_Extent_Selection_Path, FigureExtent_KeyField, value)
        Select_and_Append(SecondaryBoundarypath, Figure_Extent_Selection_Path, Secondary_Boundary_Selection_Path,clause)

    print "......................................................................Part 2 Runtime: {} (Total Runtime: {})".format(datetime.now()-part2time, datetime.now()-startTime)
    arcpy.AddMessage("......................................................................Part 2 Runtime: {} Total Runtime: {})".format(datetime.now()-part2time, datetime.now()-startTime))

    #..............................................................................................................................
    # PART 3
    # Sample Check - Part of the program that goes through the each group of samples in the boundary extent feature class and compares it against the Report Sample FC.
    # 
    # To find the difference between the Report Sample FC and the Sample Bucket FC, a spatial selection is performed to select samples in
    # in the oundary extent FC that intersetct the Report sample FC.  An inverse selection is performed which now selects features that were
    # not selected in the intersection.  This selection are the new samples that will be added to the Report sample FC.
    #..............................................................................................................................
    part3time = datetime.now()
    print "Part 3: Find new features in each figure...\n...\n...\n..."
    arcpy.AddMessage("Part 3: Find new feautres in each figure...\n...\n...\n...")

    #create feature class layer for the Sample Check FC
    OutputLayer_Feature_Check_Selection = Feature_Check_Selection + "_Layer"
    Create_FL(OutputLayer_Feature_Check_Selection,Feature_Check_Selection_Path,"")

    #Counter for # of new locations found
    count = 0
    for value in FigureList:
        arcpy.AddMessage("Checking for new features in figure...................." + str(value))
        print "Checking for new features in figure...................." + str(value)
        clause = buildWhereClause(ChildPath, FigureExtent_KeyField, value)
        FC_Exist(TempCheck, in_mem_path, ChildPath)
        count = Find_New_Features(ChildPath, Secondary_Boundary_Selection_Path, TempCheck_Path, OutputLayer_Feature_Check_Selection, clause, count)
    arcpy.Delete_management(TempCheck_Path)
    arcpy.Delete_management(OutputLayer_Feature_Check_Selection)
    arcpy.AddMessage("...\n...\nA total of {} new features were found which are stored in the Feature Class:\n     {} \nat the following path:\n     {}".format(count,Feature_Check_Selection,Scratch_FDPath))
    

    print "......................................................................Part 3 Runtime: {} (Total Runtime: {})".format(datetime.now()-part3time, datetime.now()-startTime)
    arcpy.AddMessage("......................................................................Part 3 Runtime: {} (Total Runtime: {})".format(datetime.now()-part3time, datetime.now()-startTime))

except Exception, e:
    # If an error occurred, print line number and error message
    import traceback, sys
    tb = sys.exc_info()[2]
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exc()
    tb_error = traceback.format_tb(exc_traceback)
    print "line %i" % tb.tb_lineno
    arcpy.AddMessage("line %i" % tb.tb_lineno)
    for item in tb_error:
        print item
        arcpy.AddMessage(item)
    print e.message
    arcpy.AddMessage(e.message)

