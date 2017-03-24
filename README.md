[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/LREN-CHUV/data-factory-airflow-dags/blob/master/LICENSE) [![Codacy Badge](https://api.codacy.com/project/badge/Grade/b8a8557738114e4f819c0f2a91ba996a)](https://www.codacy.com/app/hbp-mip/data-factory-airflow-dags?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=LREN-CHUV/data-factory-airflow-dags&amp;utm_campaign=Badge_Grade) [![Code Health](https://landscape.io/github/LREN-CHUV/data-factory-airflow-dags/master/landscape.svg?style=flat)](https://landscape.io/github/LREN-CHUV/data-factory-airflow-dags/master)

# Airflow MRI preprocessing DAGs

Requirements:

* airflow-imaging-plugins
* mri-preprocessing-pipeline
* data-tracking

## Setup and configuration

### Airflow setup for MRI scans pipeline:

* Create the following pools:
    * image_preprocessing with N slots, where N is less than the number of vCPUs available on the machine
    * remote_file_copy with N slots, where N should be 1 or 2 to avoid saturating network IO

* In Airflow config file, add a [spm] section with the following entries:
    * SPM_DIR: path to the root folder of SPM 12.

* In Airflow config file, add a [mipmap] section with the following entries (required only if MipMap is used for ETL):
   * DB_CONFIG_FILE: path to the configuration file used by MipMap to connect to its work database.

* In Airflow config file, add a [data-factory] section with the following entries:
    * DATASETS: comma separated list of datasets to process. Each dataset is configured using a [&lt;dataset&gt;] section in the config file
    * EMAIL_ERRORS_TO: email address to send errors to
    * SLACK_CHANNEL: optional, Slack channel to use to send status messages
    * SLACK_CHANNEL_USER: optional, user to post as in Slack
    * SLACK_TOKEN: optional, authorisation token for Slack
    * DATA_CATALOG_SQL_ALCHEMY_CONN: connection URL to the Data catalog database tracking artifacts generated by the MRI pipelines.
    * I2B2_SQL_ALCHEMY_CONN: connection URL to the I2B2 database storing all the MRI pipelines results.

* For each dataset, add a [data-factory:&lt;dataset&gt;] section, replacing &lt;dataset&gt; with the name of the dataset and define the following entries:
    * DATASET_LABEL: Name of the dataset


* For each dataset, now configure the [data-factory:&lt;dataset&gt;:preprocessing] section:
    * INPUT_FOLDER: Folder containing the original imaging data to process. This data should have been already anonymised by a tool
    * INPUT_CONFIG: List of flags defining how incoming imaging data are organised, values are
      * boost: (optional) When enabled, we consider that all the files from a same folder share the same meta-data. The processing is (about 2 times) faster. This option is enabled by default.
      * session_id_by_patient: Rarely, a data set might use study IDs which are unique by patient (not for the whole study). E.g.: LREN data. In such a case, you have to enable this flag. This will use PatientID + StudyID as a session ID.
      * visit_id_in_patient_id: Rarely, a data set might mix patient IDs and visit IDs. E.g. : LREN data. In such a case, you have to enable this flag. This will try to split PatientID into VisitID and PatientID.
      * visit_id_from_path: Enable this flag to get the visit ID from the folder hierarchy instead of DICOM meta-data (e.g. can be useful for PPMI).
      * repetition_from_path: Enable this flag to get the repetition ID from the folder hierarchy instead of DICOM meta-data (e.g. can be useful for PPMI).
    * MAX_ACTIVE_RUNS: maximum number of folders containing scans to pre-process in parallel
    * MIN_FREE_SPACE: minimum percentage of free space available on local disk
    * MISC_LIBRARY_PATH: path to the Misc&Libraries folder for SPM pipelines.
    * PIPELINES_PATH: path to the root folder containing the Matlab scripts for the pipelines
    * PROTOCOLS_DEFINITION_FILE: path to the default protocols definition file defining the protocols used on the scanner.
    * SCANNERS: List of methods describing how the preprocessing data folder is scanned for new work, values are
      * continuous: input folder is scanned frequently for new data. Sub-folders should contain a .ready file to indicate that processing can be performed on that folder.
      * daily: input folder contains a sub-folder for the year, this folder contains daily sub-folders for each day of the year (format yyyyMMdd). Those daily sub-folders in turn contain the folders for each scan to process.
      * flat: input folder contains a set of sub-folders each containing a scan to process.
    * PIPELINES: List of pipelines to execute. Values are
      * copy_to_local: if used, input data are first copied to a local folder to speed-up processing.
      * dicom_organiser: reorganise DICOM files in a scan folder for the following pipelines.
      * dicom_selection
      * dicom_to_nifti
      * nifti_organiser
      * nifti_selection
      * mpm_maps
      * neuro_morphometric_atlas
      * export_features


* If copy_to_local is used, configure the [data-factory:&lt;dataset&gt;:preprocessing:copy_to_local] section:
    * OUTPUT_FOLDER: destination folder for the local copy

* If dicom_organiser is used, configure the [data-factory:&lt;dataset&gt;:preprocessing:dicom_organiser] section:
    * OUTPUT_FOLDER: destination folder for the organised images
    * OUTPUT_FOLDER_STRUCTURE: folder hierarchy (e.g. 'PatientID:AcquisitionDate:SeriesDescription:SeriesDate')
    * DOCKER_IMAGE: Docker image of the hierarchizer program
    * DOCKER_INPUT_DIR: Input directory inside the Docker container. Default to '/input_folder'
    * DOCKER_OUTPUT_DIR: Output directory inside the Docker container. Default to '/output_folder'

* If dicom_selection is used, configure the [data-factory:&lt;dataset&gt;:preprocessing:dicom_selection] section:
    * OUTPUT_FOLDER: destination folder for the selected images
    * IMAGES_SELECTION_CSV_PATH: path to the CSV file containing the list of selected images (PatientID | ImageID).

* If dicom_select_T1 is used, configure the [data-factory:&lt;dataset&gt;:preprocessing:dicom_select_T1] section:
    * OUTPUT_FOLDER: destination folder for the selected T1 images
    * SPM_FUNCTION: SPM function called. Default to 'selectT1'
    * PIPELINE_PATH: path to the folder containing the SPM script for this pipeline. Default to PIPELINES_PATH + '/SelectT1_Pipeline'
    * MISC_LIBRARY_PATH: path to the Misc&Libraries folder for SPM pipelines. Default to MISC_LIBRARY_PATH value in [data-factory:&lt;dataset&gt;:preprocessing] section.
    * PROTOCOLS_DEFINITION_FILE: path to the Protocols definition file defining the protocols used on the scanner. For PPMI data, SelectT1 requires a custom Protocols_definition_PPMI.txt file.

* If dicom_to_nifti is used or required (when DICOM images are used as input), configure the [data-factory:&lt;dataset&gt;:preprocessing:dicom_to_nifti] section:
    * OUTPUT_FOLDER: destination folder for the Nifti images
    * BACKUP_FOLDER: backup folder for the Nitfi images
    * SPM_FUNCTION: SPM function called. Default to 'DCM2NII_LREN'
    * PIPELINE_PATH: path to the folder containing the SPM script for this pipeline. Default to PIPELINES_PATH + '/Nifti_Conversion_Pipeline'
    * MISC_LIBRARY_PATH: path to the Misc&Libraries folder for SPM pipelines. Default to MISC_LIBRARY_PATH value in [data-factory:&lt;dataset&gt;:preprocessing] section.
    * PROTOCOLS_DEFINITION_FILE: path to the Protocols definition file defining the protocols used on the scanner. Default to PROTOCOLS_DEFINITION_FILE value in [data-factory:&lt;dataset&gt;:preprocessing] section.
    * DCM2NII_PROGRAM: Path to DCM2NII program. Default to PIPELINE_PATH + '/dcm2nii'

* If nifti_organiser is used, configure the [data-factory:&lt;dataset&gt;:preprocessing:nifti_organiser] section:
    * OUTPUT_FOLDER: destination folder for the organised images
    * OUTPUT_FOLDER_STRUCTURE: folder hierarchy (e.g. 'PatientID:AcquisitionDate:SeriesDescription:SeriesDate')
    * DOCKER_IMAGE: Docker image of the hierarchizer program
    * DOCKER_INPUT_DIR: Input directory inside the Docker container. Default to '/input_folder'
    * DOCKER_OUTPUT_DIR: Output directory inside the Docker container. Default to '/output_folder'

* If nifti_selection is used, configure the [data-factory:&lt;dataset&gt;:preprocessing:nifti_selection] section:
    * OUTPUT_FOLDER: destination folder for the selected images
    * CSV_PATH: path to the CSV file containing the list of selected images (PatientID | ImageID).

* If mpm_maps is used, configure the [data-factory:&lt;dataset&gt;:preprocessing:mpm_maps] section:
    * OUTPUT_FOLDER: destination folder for the MPMs and brain segmentation
    * BACKUP_FOLDER: backup folder for the MPMs and brain segmentation
    * SPM_FUNCTION: SPM function called. Default to 'Preproc_mpm_maps'
    * PIPELINE_PATH: path to the folder containing the SPM script for this pipeline. Default to PIPELINES_PATH + '/MPMs_Pipeline'
    * MISC_LIBRARY_PATH: path to the Misc&Libraries folder for SPM pipelines. Default to MISC_LIBRARY_PATH value in [data-factory:&lt;dataset&gt;:preprocessing] section.
    * PROTOCOLS_DEFINITION_FILE: path to the Protocols definition file defining the protocols used on the scanner. Default to PROTOCOLS_DEFINITION_FILE value in [data-factory:&lt;dataset&gt;:preprocessing] section.

* If neuro_morphometric_atlas is used, configure the [data-factory:&lt;dataset&gt;:preprocessing:neuro_morphometric_atlas] section:
    * OUTPUT_FOLDER: destination folder for the Atlas File, the volumes of the Morphometric Atlas structures (.txt), the csv file containing the volume, and globals plus Multiparametric Maps (R2*, R1, MT, PD) for each structure defined in the Subject Atlas.
    * BACKUP_FOLDER: backup folder for the Atlas File, the volumes of the Morphometric Atlas structures (.txt), the csv file containing the volume, and globals plus Multiparametric Maps (R2*, R1, MT, PD) for each structure defined in the Subject Atlas.
    * SPM_FUNCTION: SPM function called. Default to 'NeuroMorphometric_pipeline'
    * PIPELINE_PATH: path to the folder containing the SPM script for this pipeline. Default to PIPELINES_PATH + '/NeuroMorphometric_Pipeline/NeuroMorphometric_tbx/label'
    * MISC_LIBRARY_PATH: path to the Misc&Libraries folder for SPM pipelines. Default to MISC_LIBRARY_PATH value in [data-factory:&lt;dataset&gt;:preprocessing] section.
    * PROTOCOLS_DEFINITION_FILE: path to the Protocols definition file defining the protocols used on the scanner. Default to PROTOCOLS_DEFINITION_FILE value in [data-factory:&lt;dataset&gt;:preprocessing] section.
    * TPM_TEMPLATE: Path to the the template used for segmentation step in case the image is not segmented. Default to SPM_DIR + 'tpm/nwTPM_sl3.nii'

* For each dataset, now configure the [data-factory:&lt;dataset&gt;:ehr] section:
    * INPUT_FOLDER: Folder containing the original EHR data to process. This data should have been already anonymised by a tool
    * INPUT_FOLDER_DEPTH: When a flat scanner is used, indicates the depth of folders to traverse before reaching EHR data. Default to 1.
    * MIN_FREE_SPACE: minimum percentage of free space available on local disk
    * SCANNERS: List of methods describing how the EHR data folder is scanned for new work, values are
      * daily: input folder contains a sub-folder for the year, this folder contains daily sub-folders for each day of the year (format yyyyMMdd). Those daily sub-folders in turn contain the EHR files in CSV format to process.
      * flat: input folder contains the EHR files in CSV format to process.
    * PIPELINES: List of pipelines to execute. Values are
      * map_ehr_to_i2b2: .

* Configure the [data-factory:&lt;dataset&gt;:ehr:map_ehr_to_i2b2] section:
    * DOCKER_IMAGE: Docker image of the tool that maps EHR data to an I2B2 schema.

* Configure the [data-factory:&lt;dataset&gt;:ehr:version_incoming_ehr] section:
    * OUTPUT_FOLDER: output folder used to store versioned EHR data.

Sample configuration:

```

[data-factory]
datasets = main
email_errors_to =
mipmap_db_confile_file = /dev/null
slack_channel = #data
slack_channel_user = Airflow
slack_token =
sql_alchemy_conn = postgresql://data_catalog:datacatalogpwd@demo:4321/data_catalog
[data-factory:main]
dataset = Demo
dataset_config = boost
dicom_files_pattern = **/*.dcm
dicom_local_folder = /data/incoming
dicom_select_T1_local_folder = /data/select_T1
dicom_select_T1_protocols_file = /opt/airflow-scripts/mri-preprocessing-pipeline/Protocols_definition.txt
ehr_data_folder = /data/ehr_demo
ehr_data_folder_depth = 0
ehr_scanners = flat
ehr_to_i2b2_capture_docker_image = hbpmip/mipmap-demo-ehr-to-i2b2:0.1
ehr_to_i2b2_capture_folder = /data/ehr_i2b2_capture
ehr_versioned_folder = /data/ehr_versioned
images_organizer_data_structure = PatientID:AcquisitionDate:SeriesDescription:SeriesDate
images_organizer_dataset_type = DICOM
images_organizer_docker_image = hbpmip/hierarchizer:latest
images_organizer_local_folder = /data/organizer
images_selection_csv_path = /data/incoming/images_selection.csv
images_selection_local_folder = /data/images_selection
max_active_runs = 30
min_free_space_local_folder = 0.3
mpm_maps_local_folder = /data/mpm_maps
mpm_maps_server_folder =
neuro_morphometric_atlas_TPM_template = /opt/spm12/tpm/nwTPM_sl3.nii
neuro_morphometric_atlas_local_folder = /data/neuro_morphometric_atlas
neuro_morphometric_atlas_server_folder =
nifti_local_folder = /data/nifti
nifti_server_folder =
pipelines_path = /opt/airflow-scripts/mri-preprocessing-pipeline/Pipelines
preprocessing_data_folder = /data/demo
preprocessing_pipelines = dicom_organizer,images_selection,dicom_select_T1,dicom_to_nifti,mpm_maps,neuro_morphometric_atlas
preprocessing_scanners = flat
protocols_file = /opt/airflow-scripts/mri-preprocessing-pipeline/Protocols_definition.txt

```
