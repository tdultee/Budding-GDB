#..............................................................................................................................
# Creator - Seth Docherty
# Date - 04/12/2015
# Purpose - Update a GIS table with data saved in a .csv files.  The .csv file can consist of data that a user manually inputs or
#           a query from a database.
#
#           The script starts by checking the input file for the following:
#               - Do the field names match the ArcMap Table.
#               - Are all the fields from the ArcMap table in the input file.
#               - Do the field types fromt the input file match the ArcMap table.
#
#           Once all the checks pass, the input file columns are reordered to match the ArcMap Table. The input file is then compared to
#           the ArcMap table to find new records.  The new records are exported to a temporary .csv file, imported into ArcMap using the
#           TabletoTable_Conversion tool, and appened to ArcMap table.
#
# Log:
#       1. Complete overhaul of code. 08/12/2016
#
#..............................................................................................................................
import os, csv, arcpy, sys, operator
from datetime import datetime
from os.path import split, join
from string import replace
from helper import *
arcpy.env.overwriteOutput = True

#Reorder columns of .csv file to match a specific format
def Reorder_InputFile(input_file,header,csv_fields):
    header = schema_header_check(header, csv_fields)
    reader = csv.reader(open(input_file,'Ur'))
    output_file_path = os.path.join(os.path.dirname(os.path.normpath(input_file)),"reorder.csv")
    output_file = open(output_file_path,'wb')
    writer = csv.writer(output_file)
    readnames = reader.next()
    name2index = dict((name, index) for index, name in enumerate(readnames))
    writeindices = [name2index[name] for name in header]
    reorderfunc = operator.itemgetter(*writeindices)
    writer.writerow(header)
    for row in reader:
        writer.writerow(reorderfunc(row))
    output_file.close()
    return output_file_path

def FC_Field_Type_Check(fc1,fc2):
    fix_fields=[]
    fc1_fields = Extract_Field_NameType(fc1)
    fc2_fields = Extract_Field_NameType(fc2)
    for x,y in zip(fc1_fields,fc2_fields):
        if x != y:
            fix_fields.append(x)
    if len(fix_fields) != 0:
        print "\nPlease check the schema.ini file located in the same folder as the input .csv file."
        print "The following field(s) need to be to be fixed with the proper field type(s) ......\n "
        print ("{0:<20} {1:>20}".format("Field Name:","Field Type"))
        arcpy.AddWarning("\nPlease check the schema.ini file located in the same folder as the input .csv file.")
        arcpy.AddWarning("The following field(s) need to be to be fixed with the proper field type(s)......\n ")
        arcpy.AddMessage(("{0:<20} {1:>20}".format("Field Name:","Field Type")))
        for field,type in fix_fields:
            print ("{0:<20} {1:>20}".format(field,type))
            arcpy.AddMessage(("{0:<20} {1:>20}".format(field,type)))
        print "\n"
        arcpy.AddMessage("\n")
        sys.exit()

def create_schema_file(file_path, fields, csv_fields):
    name=[]
    type=[]
    for a,b in fields:
        name.append(a)
        if b == 'String':
            type.append('Text')
        elif b == "SmallInteger":
            type.append('Short')
        elif b == "Integer":
            type.append('Long')
        else:
            type.append(b)
    name = schema_header_check(name, csv_fields)    
    fields=zip(name,type)
    
    directory = os.path.dirname(os.path.normpath(file_path))
    print ("Creating schema.ini file in {}".format(directory))
    arcpy.AddMessage(("Creating schema.ini file in {}".format(directory)))
    schema = directory + "\schema.ini"

    # Set new schema.ini
    schema_file = open(schema,"w")
    schema_file.write("[" + os.path.basename(os.path.normpath(file_path)) + "]\n")
    #schema_file.write("Format=Delimited(,) .csv"
    #schema_file.write("MaxScanRows=0\n") https://gisnuts.com/terra/blog/2012/06/14/using-the-schemaini-file-to-import-a-csv-file-into-arcgis
    x=1
    for name,type in fields:
        if name.find(" ") > 0:
            schema_file.write("Col{}=".format(x)+'"{}"'.format(name) + " {}\n".format(type))
        else:
            schema_file.write(r"Col{}="'{}'" {}\n".format(x,name,type))
        x += 1

    schema_file.close()

def schema_header_check(fc_header, csv_header):
    revised_name=[]
    for fc_name in fc_header:
        for file_name in csv_header:
            if file_name == fc_name:
                revised_name.append(fc_name)
            else:
                file_name2 = file_name.replace(' ','_')
                if file_name2 == fc_name:
                    revised_name.append(file_name)
    return revised_name

startTime = datetime.now()
print startTime

try:

    #..............................................................................................................................
    #User Input data
    #..............................................................................................................................

    FILE_INPUTPATH = arcpy.GetParameterAsText(0) #Inputpath for .csv file
    FC_INPUTPATH = arcpy.GetParameterAsText(1) # Inputpath for Feature Class
    INPUT_SCRATCHGDB= arcpy.GetParameterAsText(2) #Input Scratch GDB

    #..............................................................................................................................
    #Hard Coded Data
    #..............................................................................................................................

    #Check if there is a filepath from the input layers. If not, pre-pend the path. Also extract the FC names.
    FC_PATH, FC_NAME = InputCheck(FC_INPUTPATH)

    #Extracting File Paths for Feature Dataset and Scratch File Geodatabase
    arcpy.env.Workspace = INPUT_SCRATCHGDB
    Scratch_GDBPath, ScratchGDBName = InputCheck(INPUT_SCRATCHGDB)

    #..............................................................................................................................
    #Preping Data
    #..............................................................................................................................

    # Extract Field Info from input FC and input file
    FIELD_INFO = Extract_Field_NameType(FC_PATH)
    header=[]
    for name,type in FIELD_INFO:
        header.append(name)

    csv_header = Extract_File_Records(FILE_INPUTPATH).pop(0)
    input_list_header = remove_space(csv_header)

    # check to see if all the fields in the input file match the files in the ArcMap Table. The difference are the fields that
    # were not matched in the ArcMap table.
    field_check = list(set(header)-set(input_list_header))
    if len(field_check) != 0:
        print "Format error....\n Missing the following fields from the input .csv file: "
        arcpy.AddWarning("Format error....\n Missing the following fields from the input .csv file: ")
        for item in field_check:
            print item
            arcpy.AddMessage(item)
        sys.exit()

    #Reorder fields in the inputfile to ensure it matches the FC field order and create schema.ini file.
    file_input_reorder = Reorder_InputFile(FILE_INPUTPATH,header, csv_header)
    create_schema_file(file_input_reorder,FIELD_INFO,csv_header)

    #Import .csv to a temp ArcMap table in the user specified scratch FD.
    temp_table = FC_NAME + "_temp"
    temp_table_path = os.path.join(Scratch_GDBPath,temp_table)
    if arcpy.Exists(temp_table_path):
        arcpy.Delete_management(temp_table_path)
    arcpy.TableToTable_conversion(file_input_reorder,Scratch_GDBPath,temp_table,"")

    #Check the fields in in the INPUT FC and the temp fc (temp ArcMap table to that is imported
    FC_Field_Type_Check(FC_PATH,temp_table_path)

    #Create empty lists to store records from the 2 ArcMap tables and Extract Records.
    file_list = Extract_Table_Records(temp_table_path)
    fc_list = Extract_Table_Records(FC_PATH)

    #Find Difference between the two lists and export to temp output file if there is a difference
    difference = list(set(file_list) - set(fc_list))
    if len(difference) == 0:
        print "No new record(s) to add"
        arcpy.AddMessage("No new record(s) to add")
    else:
        #Properties for the temp .csv file output
        OUTFILE_PATH = os.path.join(os.path.dirname(os.path.normpath(FILE_INPUTPATH)),"new_records.csv")
        OUTFILE = open(OUTFILE_PATH, 'wb')
        try:
            OUTPUT = csv.writer((OUTFILE), delimiter=',', quoting=csv.QUOTE_NONE) #, quotechar='') #dialect='excel', 
        except:
            import traceback, sys
            tb = sys.exc_info()[2]
            arcpy.AddWarning('  If you get the following error:  "Error: need to escape, but no escape char set" \
                            \n  Try setting quoting=csv.QUOTE_NONNUMERIC, QUOTE_MINIMAL or QUOTE_ALL on line {} of this script \
                            \n  Quoting is currently set to QUOTE_NONE'.format(tb.tb_lineno))
            sys.exit()

        print "A total of " + str(len(difference)) + " new record(s) were found.  The new record(s) are:"
        arcpy.AddMessage("A total of " + str(len(difference)) + " new records were found.  The new records are:")
        #difference = sorted(difference, key=lambda sl: sl[0])
        for item in difference:
            arcpy.AddMessage(item)
        difference.insert(0,header)
        for item in difference:
            OUTPUT.writerow(item)
        #OUTPUT.writerows(difference)
        OUTFILE.close()

        create_schema_file(OUTFILE_PATH,FIELD_INFO,Extract_File_Records(OUTFILE_PATH).pop(0))

        #Import temp .csv to a temp ArcMap table in the user specified scratch FD and append to final ArcMap table.
        if arcpy.Exists(os.path.join(Scratch_GDBPath,FC_NAME + "_Difference")):
            arcpy.Delete_management(os.path.join(Scratch_GDBPath,FC_NAME + "_Difference"))
        arcpy.TableToTable_conversion(OUTFILE_PATH,Scratch_GDBPath, FC_NAME + "_Difference")
        arcpy.AddMessage("\nAppending the new record(s) to " + FC_NAME)
        print "\nAppending the new record(s) to " + FC_NAME
        arcpy.Append_management(os.path.join(Scratch_GDBPath,FC_NAME + "_Difference"),FC_PATH,"NO_TEST","","")

    #Remove Temporary Feature Classes from GDB and Temporary Files
    if arcpy.Exists(os.path.join(Scratch_GDBPath,FC_NAME + "_Difference")):
        arcpy.Delete_management(os.path.join(Scratch_GDBPath,FC_NAME + "_Difference"))
    if arcpy.Exists(temp_table_path):
        arcpy.Delete_management(temp_table_path)
    if os.path.exists(file_input_reorder):
        os.remove(file_input_reorder)
    try:
        if os.path.exists(OUTFILE_PATH):
            os.remove(OUTFILE_PATH)
    except:
        pass

    print "Temporary files and GDB tables have been deleted"
    arcpy.AddMessage("Temporary files and GDB tables have been deleted")

    print "......................................................................End Runtime: ", datetime.now()-startTime
    arcpy.AddMessage("......................................................................End Runtime: " + str(datetime.now()-startTime))

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