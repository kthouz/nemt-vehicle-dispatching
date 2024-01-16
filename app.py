import helpers

import logging
import json
import gradio as gr
import pandas as pd
import numpy as np

from typing import List, Tuple, Any, Union, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DATA = {
    'vehicle': pd.DataFrame(columns=["vehicle_id" ,"address", "capacity", "skills"]),
    'job': pd.DataFrame(columns=["job_id", "pickup_address", "delivery_address", "nb_passengers", "pickup_time"])
}

def guess_obj_name(obj:gr.Markdown)->str:
    """
    Guess object name from dataframe

    Parameters
    ----------
    obj: gr.Markdown


    Returns
    -------
    str
        Object name
    """
    if 'vehicle' in obj.lower():
        return 'vehicle'
    elif 'job' in obj.lower():
        return 'job'
    else:
        raise ValueError(f"Could not guess object name from {obj.value}")

def upload_file(files:gr.File, label:gr.Markdown) -> pd.DataFrame:
    """
    Upload files to dataframe

    Parameters
    ----------
    files : gr.Files
        Files to upload
    label : gr.Markdown
        Label to update
    obj_name : str, optional
        Object name, by default None

    Returns
    -------
    List[str]
        File paths
    """
    obj_name = guess_obj_name(label)
    if files is None:
        return DATA[obj_name]
    file_paths = [file.name for file in files]
    dataframes = [pd.read_csv(file_path) for file_path in file_paths]
    data = pd.concat(dataframes)
    DATA[obj_name] = data
    return data

def save_changes(df:pd.DataFrame, label:gr.Markdown) -> str:
    """
    Save changes to dataframe
    
    Parameters
    ----------
    df : pd.DataFrame
        dataframe to save
    label : gr.Markdown
        Label to update
    """
    obj_name = guess_obj_name(label)
    assert isinstance(df, pd.DataFrame), f"Expected pd.DataFrame, got {type(df)} instead"
    assert sorted(df.columns) == sorted(DATA[obj_name].columns), f"Columns do not match: {df.columns} != {DATA[obj_name].columns}"

    # drop all rows entirely filled with NaN or all empty strings
    df = df.dropna(how='all').replace('', np.nan).dropna(how='all')
    
    if len(df)==0:
        return "No changes to save"
    
    DATA[obj_name] = df
    return f"Changes saved: {len(df)} rows added/updated"

with gr.Blocks() as demo:
    gr.Markdown("## Vehicle Routing")
    with gr.Tab("Vehicles"):
        with gr.Row():
            veh_input = gr.Files(data_types=["csv", "json"])
        with gr.Row():
            with gr.Column(scale=1):
                veh_submit_btn = gr.Button("Submit")
            with gr.Column(scale=6):
                gr.Markdown("")
        with gr.Row():
            veh_label = gr.Markdown("### Vehicles")
        with gr.Row():
            veh_output = gr.Dataframe(DATA.get('vehicle'), interactive=True, elem_id="vehicle-output")
        with gr.Row():
            with gr.Column(scale=1):
                veh_save_btn = gr.Button("Save Changes")
            with gr.Column(scale=6):
                gr.Markdown("")
        with gr.Row():
            veh_status_text = gr.Markdown("")
    with gr.Tab("Jobs"):
        with gr.Row():
            job_input = gr.Files(data_types=["csv", "json"])
        with gr.Row():
            with gr.Column(scale=1):
                job_submit_btn = gr.Button("Submit")
            with gr.Column(scale=6):
                gr.Markdown("")
        with gr.Row():
            job_label = gr.Markdown("### Jobs")
        with gr.Row():
            job_output = gr.Dataframe(DATA.get('job'), interactive=True, elem_id="job-output")
        with gr.Row():
            with gr.Column(scale=1):
                job_save_btn = gr.Button("Save Changes")
            with gr.Column(scale=6):
                gr.Markdown("")
        with gr.Row():
            job_status_text = gr.Markdown("")
    with gr.Tab("Optimization"):
        with gr.Row():
            with gr.Column(scale=2):
                optimize_button = gr.Button("Optimize")
            with gr.Column(scale=3):
                map_output = gr.HTML(helpers.generate_generic_leafmap, label="Map")

    veh_submit_btn.click(
        fn=upload_file,
        inputs=[veh_input, veh_label],
        outputs=[veh_output]
    )
    veh_save_btn.click(
        fn=save_changes,
        inputs=[veh_output, veh_label],
        outputs=[veh_status_text]
    )
    job_submit_btn.click(
        fn=upload_file,
        inputs=[job_input, job_label],
        outputs=[job_output]
    )
    job_save_btn.click(
        fn=save_changes,
        inputs=[job_output, job_label],
        outputs=[job_status_text]
    )
    
demo.launch(debug=True)
