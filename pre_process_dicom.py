"""

Pre-process DICOM files in a study folder

"""

import logging, os
import StringIO

from datetime import datetime, timedelta
from functools import partial
from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators import SpmOperator
from airflow import configuration

from util import dicom_import
from util import nifti_import


# constants

DAG_NAME = 'pre_process_dicom'

pipelines_path = str(configuration.get('mri', 'PIPELINES_PATH'))
protocols_file = str(configuration.get('mri', 'PROTOCOLS_FILE'))
dicom_local_output_folder = str(configuration.get('mri', 'DICOM_LOCAL_OUTPUT_FOLDER'))
dicom_to_nifti_local_output_folder = str(configuration.get('mri', 'NIFTI_LOCAL_OUTPUT_FOLDER'))
dicom_to_nifti_server_output_folder = str(configuration.get('mri', 'NIFTI_SERVER_OUTPUT_FOLDER'))
dicom_to_nifti_pipeline_path = pipelines_path + '/Nifti_Conversion_Pipeline'
neuro_morphometric_atlas_local_output_folder = str(configuration.get('mri', 'NEURO_MORPHOMETRIC_ATLAS_LOCAL_OUTPUT_FOLDER'))
neuro_morphometric_atlas_server_output_folder = str(configuration.get('mri', 'NEURO_MORPHOMETRIC_ATLAS_SERVER_OUTPUT_FOLDER'))
neuro_morphometric_atlas_pipeline_path = pipelines_path + '/NeuroMorphometric_Pipeline/NeuroMorphometric_tbx/label'
mpm_maps_local_output_folder = str(configuration.get('mri', 'MPM_MAPS_LOCAL_OUTPUT_FOLDER'))
mpm_maps_server_output_folder = str(configuration.get('mri', 'MPM_MAPS_SERVER_OUTPUT_FOLDER'))
mpm_maps_pipeline_path = pipelines_path + '/MPMs_Pipeline'
misc_library_path = pipelines_path + '/../Miscellaneous&Others'


# functions

# Extract the information from DICOM files located inside a folder.
# The folder information should be given in the configuration parameter 'folder' of the DAG run
def extract_dicom_info_fn(**kwargs):
    ti = kwargs['task_instance']
    dr = kwargs['dag_run']
    session_id = dr.conf['session_id']
    input_data_folder = dicom_local_output_folder + '/' + session_id

    logging.info('folder %s, session_id %s' % (input_data_folder, session_id))

    (participant_id, scan_date) = dicom_import.visit_info(input_data_folder)
    dicom_import.dicom2db(input_data_folder)

    ti.xcom_push(key='folder', value=input_data_folder)
    ti.xcom_push(key='session_id', value=session_id)
    ti.xcom_push(key='participant_id', value=participant_id)
    ti.xcom_push(key='scan_date', value=scan_date)

    return "ok"

# Conversion pipeline from DICOM to Nifti format.
# It converts all files located in the folder 'folder'
# parent_task should contain XCOM keys 'folder' and 'session_id'
def dicom_to_nifti_pipeline_fn(parent_task, **kwargs):
    engine = kwargs['engine']
    ti = kwargs['task_instance']
    input_data_folder = ti.xcom_pull(key='folder', task_ids=parent_task)
    session_id = ti.xcom_pull(key='session_id', task_ids=parent_task)
    participant_id = ti.xcom_pull(key='participant_id', task_ids=parent_task)
    scan_date = ti.xcom_pull(key='scan_date', task_ids=parent_task)
    logging.info("DICOM to Nifti pipeline: session_id=%s, input_folder=%s" % (session_id, input_data_folder))

    out = StringIO.StringIO()
    err = StringIO.StringIO()
    parent_data_folder = os.path.abspath(input_data_folder + '/..')
    logging.info("Calling DCM2NII_LREN(%s,%s,%s,%s,%s)" % (parent_data_folder, session_id, dicom_to_nifti_local_output_folder, dicom_to_nifti_server_output_folder, protocols_file))
    success = engine.DCM2NII_LREN(
        parent_data_folder,
        session_id,
        dicom_to_nifti_local_output_folder,
        dicom_to_nifti_server_output_folder,
        protocols_file, stdout=out, stderr=err)

    logging.info("SPM output:")
    logging.info(out.getvalue())
    logging.info("SPM errors:")
    logging.info(err.getvalue())
    logging.info("SPM returned %s", success)
    if success < 1.0:
        raise RuntimeError('DICOM to Nifti pipeline failed')

    ti.xcom_push(key='folder', value=dicom_to_nifti_local_output_folder + '/' + session_id)
    ti.xcom_push(key='session_id', value=session_id)
    ti.xcom_push(key='participant_id', value=participant_id)
    ti.xcom_push(key='scan_date', value=scan_date)
    return success

# Pipeline that builds a Neuro morphometric atlas from the Nitfi files located in the folder 'folder'
# parent_task should contain XCOM keys 'folder' and 'session_id'
def neuro_morphometric_atlas_pipeline_fn(parent_task, **kwargs):
    engine = kwargs['engine']
    ti = kwargs['task_instance']
    input_data_folder = ti.xcom_pull(key='folder', task_ids=parent_task)
    session_id = ti.xcom_pull(key='session_id', task_ids=parent_task)
    participant_id = ti.xcom_pull(key='participant_id', task_ids=parent_task)
    scan_date = ti.xcom_pull(key='scan_date', task_ids=parent_task)
    logging.info("NeuroMorphometric pipeline: session_id=%s, input_folder=%s" % (session_id, input_data_folder))

    out = StringIO.StringIO()
    err = StringIO.StringIO()
    table_format='csv'
    parent_data_folder = os.path.abspath(input_data_folder + '/..')
    logging.info("Calling NeuroMorphometric_pipeline(%s,%s,%s,%s,%s,%s)" % (session_id, parent_data_folder, neuro_morphometric_atlas_local_output_folder, neuro_morphometric_atlas_server_output_folder, protocols_file, table_format))
    success = engine.NeuroMorphometric_pipeline(session_id,
        parent_data_folder,
        neuro_morphometric_atlas_local_output_folder,
        neuro_morphometric_atlas_server_output_folder,
        protocols_file,
        table_format, stdout=out, stderr=err)

    logging.info("SPM output:")
    logging.info(out.getvalue())
    logging.info("SPM errors:")
    logging.info(err.getvalue())
    logging.info("SPM returned %s", success)
    if success < 1.0:
        raise RuntimeError('NeuroMorphometric pipeline failed')

    ti.xcom_push(key='folder', value=neuro_morphometric_atlas_local_output_folder + '/' + session_id)
    ti.xcom_push(key='session_id', value=session_id)
    ti.xcom_push(key='participant_id', value=participant_id)
    ti.xcom_push(key='scan_date', value=scan_date)
    return success

# Pipeline that builds the MPM maps from the Nitfi files located in the folder 'folder'
# parent_task should contain XCOM keys 'folder' and 'session_id'
def mpm_maps_pipeline_fn(parent_task, **kwargs):
    engine = kwargs['engine']
    ti = kwargs['task_instance']
    input_data_folder = ti.xcom_pull(key='folder', task_ids=parent_task)
    session_id = ti.xcom_pull(key='session_id', task_ids=parent_task)
    pipeline_params_config_file = 'Preproc_mpm_maps_pipeline_config.txt'
    participant_id = ti.xcom_pull(key='participant_id', task_ids=parent_task)
    scan_date = ti.xcom_pull(key='scan_date', task_ids=parent_task)
    logging.info("MPM Maps pipeline: session_id=%s, input_folder=%s" % (session_id, input_data_folder))

    out = StringIO.StringIO()
    err = StringIO.StringIO()
    parent_data_folder = os.path.abspath(input_data_folder + '/..')
    logging.info("Calling Preproc_mpm_maps(%s,%s,%s,%s,%s,%s)" % (parent_data_folder, session_id, mpm_maps_local_output_folder, protocols_file, pipeline_params_config_file, mpm_maps_server_output_folder))
    success = engine.Preproc_mpm_maps(
        parent_data_folder,
        session_id,
        mpm_maps_local_output_folder,
        protocols_file,
        pipeline_params_config_file,
        mpm_maps_server_output_folder, stdout=out, stderr=err)

    logging.info("SPM output:")
    logging.info(out.getvalue())
    logging.info("SPM errors:")
    logging.info(err.getvalue())
    logging.info("SPM returned %s", success)
    if success < 1.0:
        raise RuntimeError('MPM Maps pipeline failed')

    ti.xcom_push(key='folder', value=mpm_maps_local_output_folder + '/' + session_id)
    ti.xcom_push(key='session_id', value=session_id)
    ti.xcom_push(key='participant_id', value=participant_id)
    ti.xcom_push(key='scan_date', value=scan_date)
    return success

# Extract information from the Nifti files located in the folder 'folder'
# parent_task should contain XCOM keys 'folder' and 'session_id'
def extract_nifti_info_fn(parent_task, **kwargs):
    ti = kwargs['task_instance']
    input_data_folder = ti.xcom_pull(key='folder', task_ids=parent_task)
    session_id = ti.xcom_pull(key='session_id', task_ids=parent_task)
    participant_id = ti.xcom_pull(key='participant_id', task_ids=parent_task)
    scan_date = ti.xcom_pull(key='scan_date', task_ids=parent_task)

    logging.info("NIFTI extract: session_id=%s, input_folder=%s" % (session_id, input_data_folder))

    nifti_import.nifti2db(input_data_folder, participant_id, scan_date)

    ti.xcom_push(key='folder', value=input_data_folder)
    ti.xcom_push(key='session_id', value=session_id)
    ti.xcom_push(key='participant_id', value=participant_id)
    ti.xcom_push(key='scan_date', value=scan_date)

    return "ok"


# Define the DAG

default_args = {
 'owner': 'airflow',
 'pool': 'clinical_vertex',
 'depends_on_past': False,
 'start_date': datetime.now(),
 'retries': 1,
 'retry_delay': timedelta(seconds=120),
 'email_on_failure': True,
 'email_on_retry': True
}
 
dag = DAG(
    dag_id=DAG_NAME,
    default_args=default_args,
    schedule_interval=None)

copy_dicom_to_local_cmd = """
    rsync -av {{ dag_run.conf["folder"] }} {{ params["local_output_folder"] }}/{{ dag_run.conf["session_id"] }}
"""

copy_dicom_to_local = BashOperator(
    task_id='copy_dicom_to_local',
    bash_command=copy_dicom_to_local_cmd,
    params={'local_output_folder': dicom_local_output_folder},
    dag = dag
    )

copy_dicom_to_local.doc_md = """\
# Copy DICOM files to a local drive

Speed-up the processing of DICOM files by first copying them from a shared folder to the local hard-drive.
"""

extract_dicom_info = PythonOperator(
    task_id='extract_dicom_info',
    python_callable=extract_dicom_info_fn,
    provide_context=True,
    execution_timeout=timedelta(hours=1),
    dag=dag
    )
extract_dicom_info.set_upstream(copy_dicom_to_local)

extract_dicom_info.doc_md = """\
# Extract DICOM information

Read DICOM information from the files stored in the session folder and store that information in the database.
"""

dicom_to_nifti_pipeline = SpmOperator(
    task_id='dicom_to_nifti_pipeline',
    python_callable=partial(dicom_to_nifti_pipeline_fn, 'extract_dicom_info'),
    provide_context=True,
    matlab_paths=[misc_library_path, dicom_to_nifti_pipeline_path],
    execution_timeout=timedelta(hours=3),
    dag=dag
    )

dicom_to_nifti_pipeline.set_upstream(extract_dicom_info)

dicom_to_nifti_pipeline.doc_md = """\
# DICOM to Nitfi Pipeline

This function convert the dicom files to Nifti format using the SPM tools and dcm2nii tool developed by Chris Rorden.

Webpage: http://www.mccauslandcenter.sc.edu/mricro/mricron/dcm2nii.html

"""

cleanup_local_dicom_cmd = """
    rm -rf {{ params["local_output_folder"] }}/{{ dag_run.conf["session_id"] }}
"""

cleanup_local_dicom = BashOperator(
    task_id='cleanup_local_dicom',
    bash_command=copy_dicom_to_local_cmd,
    params={'local_output_folder': dicom_local_output_folder},
    dag = dag
    )
cleanup_local_dicom.set_upstream(dicom_to_nifti_pipeline)

cleanup_local_dicom.doc_md = """\
# Cleanup local DICOM files

Remove locally stored DICOM files as they have been processed already.
"""

extract_nifti_info = PythonOperator(
    task_id='extract_nifti_info',
    python_callable=partial(extract_nifti_info_fn, 'dicom_to_nifti_pipeline'),
    provide_context=True,
    execution_timeout=timedelta(hours=1),
    dag=dag
    )

extract_nifti_info.set_upstream(dicom_to_nifti_pipeline)

extract_nifti_info.doc_md = """\
# Extract information from NIFTI files converted from DICOM

Read NIFTI information from a directory tree of nifti files freshly converted from DICOM and store that information in the database.
"""

mpm_maps_pipeline = SpmOperator(
    task_id='mpm_maps_pipeline',
    python_callable=partial(mpm_maps_pipeline_fn, 'extract_nifti_info'),
    provide_context=True,
    matlab_paths=[misc_library_path, mpm_maps_pipeline_path],
    execution_timeout=timedelta(hours=3),
    dag=dag
    )

mpm_maps_pipeline.set_upstream(extract_nifti_info)

mpm_maps_pipeline.doc_md = """\
# MPM Maps Pipeline

This function computes the Multiparametric Maps (MPMs) (R2*, R1, MT, PD) and brain segmentation in different tissue maps.
All computation was programmed based on the LREN database structure. The MPMs are calculated locally in 'OutputFolder' and finally copied to 'ServerFolder'.

"""

extract_nifti_mpm_info = PythonOperator(
    task_id='extract_nifti_mpm_info',
    python_callable=partial(extract_nifti_info_fn, 'mpm_maps_pipeline'),
    provide_context=True,
    execution_timeout=timedelta(hours=1),
    dag=dag
    )

extract_nifti_mpm_info.set_upstream(mpm_maps_pipeline)

extract_nifti_mpm_info.doc_md = """\
# Extract information from NIFTI files generated by MPM pipeline

Read NIFTI information from a directory tree containing the Nifti files created by MPM pipeline and store that information in the database.
"""

neuro_morphometric_atlas_pipeline = SpmOperator(
    task_id='neuro_morphometric_atlas_pipeline',
    python_callable=partial(neuro_morphometric_atlas_pipeline_fn, 'mpm_maps_pipeline'),
    provide_context=True,
    matlab_paths=[misc_library_path, neuro_morphometric_atlas_pipeline_path],
    execution_timeout=timedelta(hours=3),
    dag=dag
    )

neuro_morphometric_atlas_pipeline.set_upstream(mpm_maps_pipeline)

neuro_morphometric_atlas_pipeline.doc_md = """\
# NeuroMorphometric Pipeline

This function computes an individual Atlas based on the NeuroMorphometrics Atlas. This is based on the NeuroMorphometrics Toolbox.
This delivers three files:

1. Atlas File (*.nii);
2. Volumes of the Morphometric Atlas structures (*.txt);
3. CSV File (.csv) containing the volume, globals, and Multiparametric Maps (R2*, R1, MT, PD) for each structure defined in the Subject Atlas.

"""

extract_nifti_atlas_info = PythonOperator(
    task_id='extract_nifti_atlas_info',
    python_callable=partial(extract_nifti_info_fn, 'neuro_morphometric_atlas_pipeline'),
    provide_context=True,
    execution_timeout=timedelta(hours=1),
    dag=dag
    )

extract_nifti_atlas_info.set_upstream(neuro_morphometric_atlas_pipeline)

extract_nifti_atlas_info.doc_md = """\
# Extract information from NIFTI files generated by Neuro Morphometrics Atlas pipeline

Read NIFTI information from a directory tree containing the Nifti files created by Neuro Morphometrics Atlas pipeline and store that information in the database.
"""
