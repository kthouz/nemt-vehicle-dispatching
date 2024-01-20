import helpers
import constants
import routing

import json
import os
import gradio as gr
import pandas as pd
import numpy as np

from gradio_calendar import Calendar
from typing import List, Tuple, Any, Union, Dict
from datetime import datetime
from loguru import logger
from tomark import tomark
from pprint import pprint

helpers.initialize_directories([constants.PREPROCESSED_STORE, constants.SOLUTION_STORE, constants.LOGS_STORE])
logger.add(os.path.join(constants.LOGS_STORE, f"{datetime.now().strftime('%Y-%m-%d')}.log"), rotation="1 day", retention="7 days", level=constants.LOG_LEVEL)

DATA = {
    # 'vehicle': pd.DataFrame(columns=["vehicle_id" ,"address", "capacity", "skills", "start_time", "end_time"]),
    # 'job': pd.DataFrame(columns=["job_id", "pickup_address", "delivery_address", "nb_passengers", "earliest_pickup", "service_time"]),
    'vehicle': pd.read_csv("data/vehicles.csv"),
    'job': pd.read_csv("data/jobs.csv"),
    'vehicle_processed': None,
    'vehicle_scheduled': [],
    'job_processed': None,
    'solution': None,
    'preprocess_errors': None,
    'id_mapper': {'vehicle': dict(), 'job': dict()},
    'routes': dict()
}
DATA['job_selected'] = DATA['job'].copy()
DATA['vehicle_selected'] = DATA['vehicle'].copy()

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

@logger.catch
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
    DATA[f"{obj_name}_selected"] = data
    return data

@logger.catch
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
    DATA[f"{obj_name}_selected"] = df
    return f"Changes saved: {len(df)} rows added/updated"

@logger.catch
def preprocess_data(session_id:str, vdf:pd.DataFrame, tasks:pd.DataFrame, task_type='shipment', use_cache:bool=True, save:bool=False)->Tuple[List[dict], List[dict], Dict[str, List[str]]]:
    if len(vdf)==0 or len(tasks)==0:
        return "Preprocessing failed: no vehicles or jobs. Please first upload vehicles and jobs.", ""
    
    dates = pd.to_datetime(tasks['latest_delivery']).dt.date.unique()
    if len(dates)>1:
        return "Preprocessing failed: multiple dates provided. Please go Jobs tab and select a single date.", ""
    else:
        date = dates[0].strftime('%Y-%m-%d')
    session_id = str(session_id).split(":")[1].strip()
    if task_type=='shipment':
        DATA['vehicle_processed'], _, DATA['job_processed'], DATA['preprocess_errors'], DATA['id_mapper'] = routing.preprocess(vdf, tasks=tasks, task_type=task_type, use_cache=use_cache, save=save, session_id=session_id)
    elif task_type=='job':
        DATA['vehicle_processed'], DATA['job_processed'], _, DATA['preprocess_errors'], DATA['id_mapper'] = routing.preprocess(vdf, tasks=tasks, task_type=task_type, use_cache=use_cache, save=save, session_id=session_id)
    else:
        raise ValueError(f"Invalid task_type: {task_type}. Expected 'shipment' or 'job'")
    nb_vehicles = len(DATA['vehicle_processed'])
    nb_jobs = len(DATA['job_processed'])


    errors = []
    for entity, items in DATA['preprocess_errors'].items():
        for id, item in items.items():
            errors.append({"id": id, "vroom_id": item['vroom_id'], "entity": entity, "error": item['error']})
    errors_table = tomark.Tomark.table(errors[:min(10, len(errors))])
    if nb_vehicles>0 and nb_jobs>0:
        status = "complete"
        action = "Proceed to optimize"
    else:
        status = "failed"
        action = "Fix errors and rerun preprocessing"
    
    res = f"- Date: {date}"
    res += f"\n- Preprocessing {status}: {nb_vehicles} vehicles & {nb_jobs} jobs."
    res += f"\n- Action: {action}"
    res += f"\n- Error count: {len(errors)}"

    if len(errors)>0:
        errors = f"### Errors\n{errors_table}"
    else:
        errors = "### Errors"
    return res, errors

@logger.catch
def update_date_selection(date:str, label:gr.Markdown='job')->None:
    obj_name = guess_obj_name(label)
    date = str(date).split(":")[0].strip()
    date = pd.to_datetime(date)
    if obj_name=='vehicle':
        return DATA[f"vehicle_selected"]
    elif obj_name=='job':
        DATA[f"job_selected"] = DATA[label].loc[pd.to_datetime(DATA[obj_name]['latest_delivery']).dt.date==date.date()]
        return DATA[f"job_selected"]

def list_dates(df:pd.DataFrame)->Dict[str, int]:
    counts = pd.DataFrame(pd.to_datetime(df['latest_delivery']).dt.date.value_counts())
    _list = [f"{row[0].strftime('%Y-%m-%d')}: {row[1]}" for row in counts.reset_index().sort_values('latest_delivery', ascending=False).values.tolist()]
    return _list

def format_summary(summary:Dict[str, Any])->str:
    s = {
        'routes': summary['routes'],
        'assigned jobs': summary['assigned'],
        'unassigned jobs': summary['unassigned'],
        'distance (mi)': int(np.ceil(summary['distance']*0.000621371)),
        'duration (min)': int(np.ceil(summary['duration'])),
        'service (min)': int(np.ceil(summary['service']/60)),
        'waiting (min)': int(np.ceil(summary['waiting_time']/60)),
    }
    text = "**Summary**"
    text += "\n" + tomark.Tomark.table([s])
    return text

def format_unassigned(df:pd.DataFrame)->str:
    df = df[['job_id', 'pickup_address', 'delivery_address', 'nb_passengers', 'earliest_pickup', 'latest_delivery']].drop_duplicates().sort_values('job_id')
    if len(df)==0:
        return "0 unassigned jobs"
    s = []
    for _, row in df.iterrows():
        s.append({
            'job_id': row['job_id'],
            'pickup_address': row['pickup_address'],
            'delivery_address': row['delivery_address'],
            'nb_passengers': row['nb_passengers'],
            'earliest_pickup': row['earliest_pickup'],
            'latest_delivery': row['latest_delivery']
        })
    text = f"**Unassigned jobs**"
    text += "\n" + tomark.Tomark.table(s)
    return text

def format_route(vehicle:str, route:List[Dict[str, Any]], jobs:pd.DataFrame, vehicles:pd.DataFrame, task_type:str='shipment')->str:
    rdf = pd.DataFrame(route)
    rdf['distance (mile)'] = (rdf['distance']*0.000621371).astype(int)
    rdf['arrival'] = pd.to_datetime(rdf['arrival'], unit='s', utc=True).dt.strftime('%Y-%m-%d %H:%M:%S')
    rdf['waiting_time (min)'] = (rdf['waiting_time']/60).astype(int)
    rdf['step'] = range(0, len(rdf))
    rdf['address'] = rdf[['id', 'type']].apply(lambda x: helpers.get_job_address(vehicle, x['id'], x['type'], jobs, vehicles, DATA['id_mapper'][task_type]), axis=1)
    rdf = rdf[['step', 'address', 'type', 'arrival', 'waiting_time (min)', 'distance (mile)']].fillna('').to_dict(orient='records')
    mrdf = tomark.Tomark.table(rdf)
    text = f"**Vehicle {vehicle}**"
    text += "\n" + mrdf
    return text

@logger.catch
def optimize(session_id:str, task_type:str='shipment', vehicles:List[dict]=DATA.get('vehicle_processed'), jobs:List[dict]=DATA.get('job_processed'), save:bool=False)->Dict[str, Any]:
    session_id = str(session_id).split(":")[1].strip()
    if vehicles is None:
        vehicles = DATA.get('vehicle_processed')
    if jobs is None:
        jobs = DATA.get('job_processed')

    if task_type=='shipment':
        solution = routing.optimize(vehicles, shipments=jobs, save=save, session_id=session_id)
        recipe = 'cpdptw'
    elif task_type=='job':
        solution = routing.optimize(vehicles, jobs=jobs, save=save, session_id=session_id)
        recipe = 'cvrp'
    else:
        raise ValueError(f"Invalid task_type: {task_type}. Expected 'shipment' or 'job'")
    DATA['solution'] = solution
    if solution is None:
        return "Optimization failed", "Optimization failed", helpers.generate_generic_leafmap()
    
    routes = dict()
    DATA['vehicle_scheduled'] = []
    for route in solution['routes']:
        _id = DATA['id_mapper']['vehicle'].get(route['vehicle'])
        routes[route['vehicle']] = {
            "duration": route['duration'],
            "vehicle_id": _id,
            "distance": route['distance'],
            "waiting_time": route['waiting_time'],
            "steps": route['steps']
        }
        DATA['vehicle_scheduled'].append(_id)
        DATA['routes'][_id] = format_route(_id, route['steps'], jobs=DATA['job_selected'], vehicles=DATA['vehicle_selected'], task_type=task_type)

    lfmap = helpers.generate_leafmap(list(routes.values()), id_mapper=DATA['id_mapper'][task_type], jobs=DATA['job_selected'], vehicles=DATA['vehicle_selected'], unassigned=solution["unassigned"], recipe=recipe, zoom=10, height="500px", width="500px")

    summary = solution['summary']
    if recipe=='cpdptw':
        summary['unassigned'] = int(summary['unassigned']/2)
    
    summary['assigned'] = len(jobs) - summary['unassigned']
    unassigned_ids = list(map(lambda x: DATA['id_mapper'][task_type].get(x['id']), solution['unassigned']))
    unassigned = DATA['job_selected'].loc[DATA['job_selected']['job_id'].isin(unassigned_ids)]

    veh_dropdown = gr.Dropdown(DATA['vehicle_scheduled'], label="Select a vehicle", elem_id="vehicle-picker", interactive=True)
    return format_summary(summary), format_unassigned(unassigned), lfmap, veh_dropdown


with gr.Blocks() as demo:
    gr.Markdown("## Vehicle Routing: Prototype")
    session_id = gr.Markdown(f"session: {str(int(datetime.timestamp(datetime.now())))}")
    with gr.Tab("Vehicles"):
        with gr.Row():
            veh_input = gr.Files(file_types=[".csv", ".json"])
        with gr.Row():
            with gr.Column(scale=1):
                veh_submit_btn = gr.Button("Submit")
            with gr.Column(scale=6):
                gr.Markdown("")
        with gr.Row():
            veh_label = gr.Markdown("### Vehicles")
        with gr.Row():
            veh_output = gr.Dataframe(
                DATA.get('vehicle'), 
                col_count=(len(constants.VEHICLES_DF_FIELDS), 'fixed'), 
                interactive=True, 
                elem_id="vehicle-output",
                datatype=["bool", "str", "str", "number", "str", "str", "str"]
                )
        with gr.Row():
            with gr.Column(scale=1):
                veh_save_btn = gr.Button("Save Changes")
            with gr.Column(scale=6):
                gr.Markdown("")
        with gr.Row():
            veh_status_text = gr.Markdown("")
    with gr.Tab("Jobs"):
        with gr.Row():
            job_input = gr.Files(file_types=[".csv", ".json"])
        with gr.Row():
            with gr.Column(scale=1):
                job_submit_btn = gr.Button("Submit")
            with gr.Column(scale=6):
                gr.Markdown("")
        with gr.Row():
            job_label = gr.Markdown("### Jobs")
        with gr.Row():
            with gr.Column(scale=1):
                # job_datepicker = Calendar("", type="datetime", label="Select a date", elem_id="job-datepicker")
                job_datepicker = gr.Dropdown(list_dates(DATA.get('job')), label="Select a date", elem_id="job-datepicker")
            with gr.Column(scale=6):
                mask_placeholder = gr.Markdown("")
        with gr.Row():
            job_output = gr.Dataframe(DATA.get('job'), col_count=(len(constants.JOBS_DF_FIELDS), 'fixed'), interactive=True, elem_id="job-output")
        with gr.Row():
            with gr.Column(scale=1):
                job_save_btn = gr.Button("Save Changes")
            with gr.Column(scale=6):
                gr.Markdown("")
        with gr.Row():
            job_status_text = gr.Markdown("")
    with gr.Tab("Optimization"):
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Row():
                    preprocess_button = gr.Button("Preprocess")
                    optimize_button = gr.Button("Optimize")
                with gr.Row():
                    process_output = gr.Markdown("")
                with gr.Row():
                    unassigned_output = gr.Markdown("")
                with gr.Row():
                    errors_output = gr.Markdown("")
            with gr.Column(scale=1):
                with gr.Row():
                    map_output = gr.HTML(helpers.generate_generic_leafmap, label="Map")
                with gr.Row():
                    summary_output = gr.Markdown("")
                with gr.Row():
                    gr.Markdown("### Routes")
                with gr.Row():
                    with gr.Column(scale=1):
                        vehicle_picker = gr.Dropdown(DATA['vehicle_scheduled'], label="Select a vehicle", elem_id="vehicle-picker", interactive=True)
                    with gr.Column(scale=1):
                        dummy_markdown = gr.Markdown("")
                with gr.Row():
                    vehicle_route = gr.Markdown("")
    with gr.Tab("Billing"):
        gr.Markdown("### Billing: In development")
        pass
                
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
    job_datepicker.change(
        fn=update_date_selection,
        inputs=[job_datepicker],
        outputs=[job_output]
    )
    job_save_btn.click(
        fn=save_changes,
        inputs=[job_output, job_label],
        outputs=[job_status_text]
    )
    preprocess_button.click(
        fn=preprocess_data,
        inputs=[session_id, veh_output, job_output],
        outputs=[process_output, errors_output]
    )
    optimize_button.click(
        fn=optimize,
        inputs=[session_id],
        outputs=[summary_output, unassigned_output, map_output, vehicle_picker]
    )
    vehicle_picker.change(
        fn=lambda x: DATA['routes'].get(x),
        inputs=[vehicle_picker],
        outputs=[vehicle_route]
    )

    


logger.info("Starting demo server...")
demo.launch(
    share=True,
    server_name=os.getenv("SERVER_NAME", "127.0.0.1"),
    server_port=int(os.getenv("SERVER_PORT", "7860")),
)
logger.info("Demo server stopped.")
