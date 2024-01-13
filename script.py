import gradio as gr
import modules.shared as shared
from pathlib import Path
import re
import json
from functools import partial
from modules.text_generation import stop_everything_event
from modules import chat

from modules import ui as main_ui
from modules.utils import gradio
from modules.extensions import apply_extensions


right_symbol = '\U000027A1'
left_symbol = '\U00002B05'
refresh_symbol = '\U0001f504'  # 🔄

def atoi(text):
    return int(text) if text.isdigit() else text.lower()

def natural_keys(text):
    return [atoi(c) for c in re.split(r'(\d+)', text)]


import os

def get_file_path(filename):
    current_directory = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(current_directory, filename)


#def get_file_path(filename):
#    return "extensions/folder/"+filename

last_save = get_file_path("last.json")
save_proj_path = get_file_path("Projects")
state_save = get_file_path("state.json")

params = {
        "display_name": "Dyna Chat",
        "is_tab": True,
        "selectA": [0,0],
        'projectname':"my_project",
        'auto_clear': True,
        'include_history': True,
        'include_history_nr':10,
        'user_tag':'>',
        'assistant_tag':'',
        'include_prompt': True,
        'include_response': True,
        'render_json': False,
        'system_prompt': 'You are a helpful AI Assistant.'
}

help_str = """
**Help**

This interface is for writing and generating dynamic blocks of text (for example scene-by-scene), that will be assembled into full text. At each generation all the previously written blocks will be inserted into LLM as a memory.
"""


# Define the global data_structure

selected_item = "History 1"
selected_item_prompt = ""
selected_item_scenetext = ""
full_text = ""

data_structure = [{"outline": selected_item, "prompt": selected_item_prompt, "scenetext": selected_item_scenetext, "is_summary": False}]

def does_outline_exist(outline_name):
    global data_structure
    return any(item["outline"] == outline_name for item in data_structure)

def get_first_outline_name():
    global data_structure
    if data_structure:
        return data_structure[0]["outline"]
    else:
        return ""  # Return None if data_structure is empty


def get_data_by_outline(outline_name):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_name:
            return item["prompt"], item["scenetext"]
    return None, None  # Return None if the outline_name is not found

def delete_item_by_outline(outline_name):
    global data_structure
    global selected_item
    next_selected_item = ""
    for item in data_structure:
        if item["outline"] == outline_name:
            data_structure.remove(item)
            selected_item = next_selected_item
            if selected_item=="" and len(data_structure)>0:
                selected_item = data_structure[0]["outline"]

            return True  # Item deleted successfully
        next_selected_item = item["outline"]
    return False  # Item not found

def generate_unique_outline_name(scene_string):
    global data_structure
    # Initialize a counter to create unique names
    counter = 1
    while True:
        outline_name = f"{scene_string} {counter}"
        # Check if the generated name is already in use
        if not any(item["outline"] == outline_name for item in data_structure):
            return outline_name
        counter += 1

def add_item(outline_name, prompt_string, scene_string):
    global data_structure
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext
    
    new_item = {"outline": outline_name, "prompt": prompt_string, "scenetext": scene_string, "is_summary": False}
    selected_item = outline_name
    selected_item_prompt = prompt_string
    selected_item_scenetext = scene_string
    
    data_structure.append(new_item)


def add_item_auto(scene_prefix, prompt_string, scene_text):
    global data_structure
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext

    # Check if data_structure has any data
    if len(data_structure)>0:
        # Get the last item in data_structure
        last_item = data_structure[-1]

        # Check if the last item has "prompt" == '' and "scenetext" == ''
        if last_item["prompt"] == '' and last_item["scenetext"] == '':
            # Overwrite the last item with new values
            last_item["prompt"] = prompt_string
            last_item["scenetext"] = scene_text
            last_item["is_summary"] = False

            # Update selected_item, selected_item_prompt, and selected_item_scenetext
            selected_item = last_item["outline"]
            selected_item_prompt = last_item["prompt"]
            selected_item_scenetext = last_item["scenetext"]
            # Update data_structure with the modified last_item
            data_structure[-1] = last_item
            return  # Exit the function without adding a new item

    outline_name = generate_unique_outline_name(scene_prefix)
    new_item = {"outline": outline_name, "prompt": prompt_string, "scenetext": scene_text, "is_summary": False}

    selected_item = outline_name
    selected_item_prompt = prompt_string
    selected_item_scenetext = scene_text

    data_structure.append(new_item)
    print (f'Adding {selected_item} with {selected_item_prompt}')


def update_item_by_outline(outline_name, new_prompt, new_scene_text):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_name:
            item["prompt"] = new_prompt
            item["scenetext"] = new_scene_text
     
            return True  # Item updated successfully
    return False  # Item not found

def update_prompt_by_outline(outline_name, new_prompt):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_name:
            item["prompt"] = new_prompt
            return True  # Item updated successfully
    return False  # Item not found

def update_scenetext_by_outline(outline_name, new_scene_text):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_name:
            item["scenetext"] = new_scene_text
            return True  # Item updated successfully
    return False  # Item not found

def generate_combined_text():
    global data_structure
    global full_text
    full_text = '\n\n'.join(item["scenetext"] for item in data_structure)
    full_text = full_text.strip()
    return full_text

def generate_combined_jsonl_w_prompt(system_prompt):
    global data_structure
    global selected_item
    global full_text 
    global params
    combined_json = []

    for item in data_structure:
        itemjson = {"messages": []}
        if system_prompt!='':
            itemjson["messages"].append(
                {"role": "system", "content": system_prompt}
            )
        itemjson["messages"].append(
            {"role": "user", "content": item["prompt"]}
        )
        itemjson["messages"].append(
            {"role": "assistant", "content": item["scenetext"]}
        )
        combined_json.append(itemjson)
    
    full_text = json.dumps(combined_json, indent=2)
    return full_text

def generate_combined_text_w_prompt():
    global data_structure
    global selected_item
    global full_text 
    global params

    if params['render_json']==True:
        return generate_combined_jsonl_w_prompt(params['system_prompt'])

    combined_text = ""
    for item in data_structure:

        prompt = ''
        response = ''

        if params['include_prompt']:
            prompt = params['user_tag'] + item["prompt"] +'\n\n'

        if params['include_response']:
            response = params['assistant_tag'] + item["scenetext"] + '\n\n'

        combined_text += prompt + response
    
    full_text = combined_text.rstrip('\n\n')  # Remove trailing newline if any

    return full_text 


def generate_combined_text_until_current_with_history(max_last):
    global data_structure
    global selected_item
    outline_name = selected_item
    count_before_outline = 0
    temp_hist = []

    if max_last > 0:
        for item in data_structure:
            if item["outline"] == outline_name:
                break  # Stop when the specified outline_name is reached

            # Check if we've reached the limit of history_number
            if count_before_outline < max_last:
                temp_hist.append(item["scenetext"])
            else:
                # If we've reached the limit, remove the oldest entry
                temp_hist.pop(0)
                temp_hist.append(item["scenetext"])

            count_before_outline += 1


    combined_text = ""
    for item_txt in temp_hist:
        combined_text += item_txt + '\n\n'
    text_until = combined_text.rstrip('\n\n')  # Remove trailing newline if any

    return text_until 


def generate_combined_text_until_current():
    global data_structure
    global selected_item
    combined_text = ""
    outline_name = selected_item
    for item in data_structure:
        if item["outline"] == outline_name:
            break  # Stop when the specified outline_name is reached
        combined_text += item["scenetext"] + '\n\n'
    text_until = combined_text.rstrip('\n\n')  # Remove trailing newline if any

    return text_until 


def move_item_up(outline_name):
    global data_structure
    for i in range(len(data_structure)):
        if data_structure[i]["outline"] == outline_name and i > 0:
            # Swap the item with the preceding one
            data_structure[i], data_structure[i - 1] = data_structure[i - 1], data_structure[i]
            return True  # Item moved up successfully
    return False  # Item not found or already at the top

def move_item_down(outline_name):
    global data_structure
    for i in range(len(data_structure) - 1):
        if data_structure[i]["outline"] == outline_name and i < len(data_structure) - 1:
            # Swap the item with the following one
            data_structure[i], data_structure[i + 1] = data_structure[i + 1], data_structure[i]
            return True  # Item moved down successfully
    return False  # Item not found or already at the bottom


class ToolButton(gr.Button, gr.components.FormComponent):
    """Small button with single emoji as text, fits inside gradio forms"""

    def __init__(self, **kwargs):
        super().__init__(variant="tool", **kwargs)

    def get_block_name(self):
        return "button"


def create_refresh_button(refresh_component, refresh_method, refreshed_args, elem_class):
    def refresh():
        refresh_method()
        args = refreshed_args() if callable(refreshed_args) else refreshed_args

        for k, v in args.items():
            setattr(refresh_component, k, v)

        return gr.update(**(args or {}))

    refresh_button = ToolButton(value=refresh_symbol, elem_classes=elem_class)
    refresh_button.click(
        fn=refresh,
        inputs=[],
        outputs=[refresh_component]
    )
    return refresh_button


def read_file_to_string(file_path):
    data = ''
    try:
        with open(file_path, 'r') as file:
            data = file.read()
    except FileNotFoundError:
        data = ''

    return data


def atoi(text):
    return int(text) if text.isdigit() else text.lower()

def save_string_to_file(file_path, string):
    try:
        with open(file_path, 'w') as file:
            file.write(string)
        print("String saved to file successfully.")
    except Exception as e:
        print("Error occurred while saving string to file:", str(e))

#last_save
def save_to_json(path_to_file):
    global data_structure
    try:
        with open(Path(path_to_file), 'w') as json_file:
            json.dump(data_structure, json_file, indent=2)
        return True    
    except:
        print(f"Saving to {path_to_file} failed")
        return False  # File not found or invalid JSON

def load_from_json(path_to_file):
    global data_structure
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext
    global full_text

    print(f"Loading project: {path_to_file}")
    try:
        with open(Path(path_to_file), 'r') as json_file:
            data_structure.clear()  # Clear existing data
            data_structure.extend(json.load(json_file))
            generate_combined_text_w_prompt()
            selected_item = get_first_outline_name()
            selected_item_prompt,selected_item_scenetext = get_data_by_outline(selected_item)

        return True  # Loading successful
    except (FileNotFoundError, json.JSONDecodeError):
        return False  # File not found or invalid JSON

def save_state():
    global params
    global state_save
    
    try:
        with open(Path(state_save), 'w') as json_file:
            json.dump(params, json_file, indent=4)
    except:
        print("Can't save last state..")

def load_state():
    global params
    global state_save
    
    try:
        with open(Path(state_save), 'r') as json_file:
            new_params = json.load(json_file)
            for item in new_params:
                params[item] = new_params[item]
    except:
        pass


last_history_visible = []
last_history_internal = []
last_undo = ""  



def get_scene_list():
    global data_structure
    return [item["outline"] for item in data_structure]

def generate_reply_wrapperMY(text_prompt, existing_text_in_output, state, _continue=False):

    global params
    global last_history_visible
    global last_history_internal
    global last_undo
    global last_save
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext
    global full_text
    global data_structure

    selF = params['selectA'][0]
    selT = params['selectA'][1]
 
    params['selectA'] = [0,0]
   
    new_version = True
    if 'turn_template' in state:
        new_version = False
    
    visible_text = None

    user_prompt = text_prompt

    text_to_keep = ""

    generate_combined_text_w_prompt()

    if new_version:
       if state['instruction_template_str']=='':
            print("Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction Template]")
            text_to_keep = existing_text_in_output + "\n Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction template]"
            yield text_to_keep, full_text
            return
    else:
        if state['turn_template']=='':
            print("Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction Template]")
            text_to_keep = existing_text_in_output + "\n Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction template]"
            yield text_to_keep, full_text
            return



    state['mode'] = 'instruct'
    
    _iswriting = "..."

    #context = state['context']
        
    if new_version:
        context_instruct = state['custom_system_message']
        contest_instruct_bk = context_instruct

        #state['custom_system_message'] = context_instruct

    else:        
        context_instruct = state['context_instruct']
        contest_instruct_bk = context_instruct

        #state['context_instruct'] = context_instruct
        

    state = apply_extensions('state', state)
    if shared.model_name == 'None' or shared.model is None:
        print("No model is loaded! Select one in the Model tab.")
        yield text_to_keep, full_text
        return
    
    output = {'visible': [], 'internal': []}    
    output['internal'].append(['', ''])
    output['visible'].append(['', ''])

    last_history = {'visible': [], 'internal': []} 

    # fill history with previous text


    outline_name = selected_item
   
    count_before_outline = 0

    if params['include_history_nr'] > 0 and params['include_history']:
        for item in data_structure:
            if item["outline"] == outline_name:
                break  # Stop when the specified outline_name is reached

            hist_prompt = item["prompt"]
            hist_response = item["scenetext"]

            # Check if we've reached the limit of history_number
            if count_before_outline < params['include_history_nr']:
                last_history['internal'].append([hist_prompt, hist_response])
                last_history['visible'].append([hist_prompt, hist_response])
            else:
                # If we've reached the limit, remove the oldest entry
                last_history['internal'].pop(0)
                last_history['visible'].pop(0)
                last_history['internal'].append([hist_prompt, hist_response])
                last_history['visible'].append([hist_prompt, hist_response])

            count_before_outline += 1


    # simple
    #story_so_far = generate_combined_text_until_current()
    #if story_so_far!="":
    #    hist_response = "Thank you, I will remember that."
    #    hist_prompt = "Here is the story so far:\n"+story_so_far
    #    last_history['internal'].append([hist_prompt, hist_response])
    #    last_history['visible'].append([hist_prompt, hist_response])

    stopping_strings = chat.get_stopping_strings(state)

    is_stream = state['stream']

  # Prepare the input
    if not _continue:
        visible_text = user_prompt

        # Apply extensions
        user_prompt, visible_text = apply_extensions('chat_input', user_prompt, visible_text, state)
        user_prompt = apply_extensions('input', user_prompt, state, is_chat=True)

        outtext = _iswriting
        yield outtext, full_text

    else:
        visible_text = user_prompt 

        if _continue:
            text_to_keep = existing_text_in_output
            # continue sel can span across squiglies
            
            # fill history for generate_chat_prompt
            #user_msg, assistant_msg
            last_history['internal'].append([user_prompt, existing_text_in_output])
            last_history['visible'].append([user_prompt, existing_text_in_output])

            outtext = text_to_keep + _iswriting   
            yield outtext, full_text


        # Generate the prompt
    kwargs = {
        '_continue': _continue,
        'history': last_history,
    }

    #prompt = apply_extensions('custom_generate_chat_prompt', question, state, **kwargs)
    
    prompt = chat.generate_chat_prompt(user_prompt, state, **kwargs)

    #put it back, just in case
    if new_version:
        state['custom_system_message'] = contest_instruct_bk
    else:    
        state['context_instruct'] = contest_instruct_bk

    # Generate
    reply = None
    for j, reply in enumerate(chat.generate_reply(prompt, state, stopping_strings=stopping_strings, is_chat=True)):

        visible_reply = reply #re.sub("(<USER>|<user>|{{user}})", state['name1'], reply)
        
        if shared.stop_everything:
            output['visible'][-1][1] = apply_extensions('output', output['visible'][-1][1], state, is_chat=True)

            output_text = output['visible'][-1][1]
            print("--Interrupted--")
            update_item_by_outline(selected_item, text_prompt, text_to_keep + output_text)
            generate_combined_text_w_prompt()
            save_to_json(last_save)

            yield  text_to_keep + output_text, full_text
            drugged_model = None
            return

        if _continue:
            output['internal'][-1] = [user_prompt,  reply]
            output['visible'][-1] = [visible_text, visible_reply]
            if is_stream:
                output_text = output['visible'][-1][1]
                update_item_by_outline(selected_item, text_prompt, text_to_keep + output_text)
                yield text_to_keep + output_text, full_text
        elif not (j == 0 and visible_reply.strip() == ''):
            output['internal'][-1] = [user_prompt, reply.lstrip(' ')]
            output['visible'][-1] = [visible_text, visible_reply.lstrip(' ')]

            if is_stream:
                output_text = output['visible'][-1][1]
                update_item_by_outline(selected_item, text_prompt, text_to_keep + output_text)
                yield  text_to_keep + output_text, full_text

    output['visible'][-1][1] = apply_extensions('output', output['visible'][-1][1], state, is_chat=True)
    
    output_text = output['visible'][-1][1]
    
    # not really used for anything
    last_history_visible = output['visible'][-1]
    last_history_internal = output['internal'][-1]
    
    update_item_by_outline(selected_item, text_prompt, text_to_keep + output_text)
    generate_combined_text_w_prompt()
    save_to_json(last_save)
    save_state()
    
    drugged_model = None

    yield  text_to_keep + output_text, full_text


def generate_reply_wrapperMY_NP(text_prompt, existing_text_in_output, state, _continue=False):

    global params
    global last_history_visible
    global last_history_internal
    global last_undo
    global last_save
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext
    global full_text
    global data_structure

    selF = params['selectA'][0]
    selT = params['selectA'][1]
 
    params['selectA'] = [0,0]
   
    new_version = True
    if 'turn_template' in state:
        new_version = False
    
    visible_text = None

    user_prompt = text_prompt

    text_to_keep = ""

    generate_combined_text_w_prompt()

    if new_version:
       if state['instruction_template_str']=='':
            print("Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction Template]")
            text_to_keep = existing_text_in_output + "\n Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction template]"
            yield text_to_keep, full_text
            return
    else:
        if state['turn_template']=='':
            print("Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction Template]")
            text_to_keep = existing_text_in_output + "\n Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction template]"
            yield text_to_keep, full_text
            return



    state['mode'] = 'instruct'
    
    _iswriting = "..."

    #context = state['context']
        
    if new_version:
        context_instruct = state['custom_system_message']
        contest_instruct_bk = context_instruct

        #state['custom_system_message'] = context_instruct

    else:        
        context_instruct = state['context_instruct']
        contest_instruct_bk = context_instruct

        #state['context_instruct'] = context_instruct
        

    state = apply_extensions('state', state)
    if shared.model_name == 'None' or shared.model is None:
        print("No model is loaded! Select one in the Model tab.")
        yield text_to_keep, full_text
        return
    
    output = {'visible': [], 'internal': []}    
    output['internal'].append(['', ''])
    output['visible'].append(['', ''])

    last_history = {'visible': [], 'internal': []} 

    # fill history with previous text
    if params['include_history_nr']>0 and params['include_history']:
        story_so_far = generate_combined_text_until_current_with_history(params['include_history_nr'])
    else:
        story_so_far = ''

    stopping_strings = chat.get_stopping_strings(state)

    is_stream = state['stream']

  # Prepare the input
    if not _continue:
        visible_text = user_prompt

        outtext = _iswriting
        yield outtext, full_text

    else:
        visible_text = user_prompt 

        if _continue:
            text_to_keep = existing_text_in_output+'\n'
            # continue sel can span across squiglies
            story_so_far = story_so_far +"\n"+ existing_text_in_output
            outtext = text_to_keep + _iswriting   
            yield outtext, full_text


        # Generate the prompt
    kwargs = {
        '_continue': _continue,
        'history': last_history,
    }

    #prompt = apply_extensions('custom_generate_chat_prompt', question, state, **kwargs)
    
    prompt = story_so_far+"\n" 
    if text_prompt!='':
        prompt = prompt + "\n"+text_prompt+"\n"

    #put it back, just in case
    if new_version:
        state['custom_system_message'] = contest_instruct_bk
    else:    
        state['context_instruct'] = contest_instruct_bk

    # Generate
    reply = None
    for j, reply in enumerate(chat.generate_reply(prompt, state, stopping_strings=stopping_strings, is_chat=False)):

        #visible_reply = re.sub("(<USER>|<user>|{{user}})", state['name1'], reply)
        visible_reply = reply
        
        if shared.stop_everything:
            output['visible'][-1][1] = apply_extensions('output', output['visible'][-1][1], state, is_chat=False)

            output_text = output['visible'][-1][1]
            print("--Interrupted--")
            update_item_by_outline(selected_item, text_prompt, text_to_keep + output_text)
            generate_combined_text_w_prompt()
            save_to_json(last_save)

            yield  text_to_keep + output_text, full_text

            return

        if _continue:
            output['internal'][-1] = [user_prompt,  reply]
            output['visible'][-1] = [visible_text, visible_reply]
            if is_stream:
                output_text = output['visible'][-1][1]
                update_item_by_outline(selected_item, text_prompt, text_to_keep + output_text)
                yield text_to_keep + output_text, full_text
        elif not (j == 0 and visible_reply.strip() == ''):
            output['internal'][-1] = [user_prompt, reply.lstrip(' ')]
            output['visible'][-1] = [visible_text, visible_reply.lstrip(' ')]

            if is_stream:
                output_text = output['visible'][-1][1]
                update_item_by_outline(selected_item, text_prompt, text_to_keep + output_text)
                yield  text_to_keep + output_text, full_text

    output['visible'][-1][1] = apply_extensions('output', output['visible'][-1][1], state, is_chat=False)
    
    output_text = output['visible'][-1][1]
    
    # not really used for anything
    last_history_visible = output['visible'][-1]
    last_history_internal = output['internal'][-1]
    
    update_item_by_outline(selected_item, text_prompt, text_to_keep + output_text)
    generate_combined_text_w_prompt()
    save_to_json(last_save)
    

    yield  text_to_keep + output_text, full_text

def custom_css():
    return """
.preview-text-drug textarea {
    background-color: #071407 !important;
    --input-text-size: 16px !important;
    color: #4dc66a !important;
    --body-text-color: #4dc66a !important;
    font-family: monospace
    
}
    """

def custom_js():
    java = '''
const drugtestElement = document.querySelector('#textbox-drugtest textarea');
let drugtestScrolled = false;

drugtestElement.addEventListener('scroll', function() {
  let diff = drugtestElement.scrollHeight - drugtestElement.clientHeight;
  if(Math.abs(drugtestElement.scrollTop - diff) <= 1 || diff == 0) {
    drugtestScrolled = false;
  } else {
    drugtestScrolled = true;
  }
});

const drugtestObserver = new MutationObserver(function(mutations) {
  mutations.forEach(function(mutation) {
    if(!drugtestScrolled) {
      drugtestElement.scrollTop = playgroundAElement.scrollHeight;
    }
  });
});

drugtestObserver.observe(drugtestElement.parentNode.parentNode.parentNode, config);

'''
    return java

#font-family: monospace
def get_available_projects():
    templpath = save_proj_path
    paths = (x for x in Path(templpath).iterdir() if x.suffix in ('.json'))
    sortedlist = sorted(set((k.stem for k in paths)), key=natural_keys)
    sortedlist.insert(0, "None")
    return sortedlist


def ui():
    global params
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext
    global full_text

    params['selectA'] = [0,0]

    load_state()
    load_from_json(last_save)


#gr_prevtext = gr.Textbox(value=full_text_until, lines = 5, max_lines=5, visible = True, label = 'Story to this point', interactive=False,elem_classes=['preview-text', 'add_scrollbar'])
#gr_itemname = gr.Textbox(value=selected_item, lines = 1, visible = True, label = 'Block', interactive=False)
    
    with gr.Tab('Generation'):
       with gr.Row():
            with gr.Column(scale = 1):
                with gr.Tab("History"):
                    with gr.Row():
                        gr_itemUp = gr.Button("Move Up") #,elem_classes="small-button"
                        gr_itemDown = gr.Button("Move Down")  
                    with gr.Row():    
                        gr_btn_del_scene = gr.Button(value='Delete',visible=True)
                        gr_btn_del_All = gr.Button(value='Clear All',visible=True)
                    gr_scenes_radio = gr.Radio(choices=get_scene_list(), value=selected_item, label='Items', interactive=True, elem_classes='checkboxgroup-table')
                    
            with gr.Column(scale = 3):
                with gr.Row():
                    with gr.Column(scale = 4):
                        gr_prompt = gr.Textbox(value=selected_item_prompt ,lines=4,visible=True, label='Prompt')
                        with gr.Row():
                            with gr.Tab('Instruction'):
                                with gr.Row():
                                    gr_btn_generate = gr.Button(value='Generate',visible=True,variant="primary")
                                    gr_btn_regenerate = gr.Button(value='Re-Generate',visible=True)
                                    gr_btn_generate_continue = gr.Button(value='Continue',visible=True)
                                    gr_btn_stop = gr.Button(value='Stop',visible=True) #elem_classes="small-button")
                            with gr.Tab('Completion'):
                                with gr.Row():
                                    gr_btn_generate_np = gr.Button(value='Complete',variant="primary", visible=True)
                                    gr_btn_regenerate_np = gr.Button(value='Re-Do Completion',visible=True)
                                    gr_btn_generate_continue_np = gr.Button(value='Continue',visible=True)
                                    gr_btn_stop_np = gr.Button(value='Stop',visible=True)
                            with gr.Tab('Settings'):
                                with gr.Row():        
                                    gr_auto_clear = gr.Checkbox(label = "Auto Clear Prompt", value = params['auto_clear'])    
                                    gr_include_history = gr.Checkbox(label = "Include History", value = params['include_history']) 
                                    include_last_history = gr.Slider(value = params['include_history_nr'],step = 1, minimum=0, maximum=50, label='Number of last History to Include')
                    with gr.Column(scale = 1):
                        gr.Markdown('')    
                with gr.Row():
                    with gr.Column(scale = 4):
                        gr_generated_text = gr.Textbox(value=selected_item_scenetext ,lines=10,visible=True, label='Generated Text',elem_classes=['textbox', 'add_scrollbar'],elem_id='textbox-drugtest')
                    with gr.Column(scale = 1):
                        gr.Markdown('')
 
    with gr.Tab('Full Conversation'):
      with gr.Row():
            with gr.Column(scale=1):
                gr_include_prompt = gr.Checkbox(value=params['include_prompt'], label='Include Prompt')
                gr_include_response = gr.Checkbox(value=params['include_response'], label='Include Response')
                gr_user_tag = gr.Textbox(value = params['user_tag'], label = "User tag", lines=1,max_lines=1)   
                gr_assistant_tag = gr.Textbox(value = params['assistant_tag'], label = "Assistant tag", lines=1,max_lines=1)
                gr_full_json = gr.Checkbox(value=params['render_json'], label='JSONL (ignores above settings)')
                gr_full_systemprompt = gr.Textbox(value = params['system_prompt'], label = "JSONL System prompt", lines=1,max_lines=1)
                gr_regenerate_full = gr.Button(value='Refresh')
            with gr.Column(scale=4):
                gr_fulltext = gr.Textbox(value=full_text,lines=25,visible=True, label='Full Text', elem_classes=['preview-text', 'add_scrollbar'])

    with gr.Tab('Project'):
        with gr.Row():
            with gr.Column(scale=1):
                gr_btn_new_prj = gr.Button(value='New Project',visible=True,variant="primary")
                with gr.Row():
                    gr_EditNewProj = gr.Button(value='Are you sure?',variant="primary",visible=False)
                    gr_EditNewProjCancel = gr.Button(value='Cancel',visible=False)
                gr_btn_saveproject = gr.Button(value='Save Project',visible=True)
                gr_EditName = gr.Textbox(value=params['projectname'],lines=1,visible=False, label='Project Name')
                with gr.Row():
                    gr_EditNameSave = gr.Button(value='Save',variant="primary",visible=False)
                    gr_EditNameCancel = gr.Button(value='Cancel',visible=False)
                gr_btn_loadproject = gr.Button(value='Load Project',visible=True)
                gr_projh_drop = gr.Dropdown(choices=['None'], label='Projects', value='None',visible=False)
                with gr.Row():
                    gr_EditNameLoad = gr.Button(value='Load',visible=False,variant="primary")
                    gr_EditNameLCancel = gr.Button(value='Cancel',visible=False)
            with gr.Column(scale=4): 
                gr.Markdown(help_str)

    def full_update_ui():
        global selected_item
        global selected_item_prompt
        global selected_item_scenetext
        global full_text

        return gr.Radio.update(choices=get_scene_list(), value=selected_item), selected_item_prompt, selected_item_scenetext,full_text



    def show_new_proj():
        return gr.Button.update(visible=True),gr.Button.update(visible=True)

    gr_btn_new_prj.click(show_new_proj, None,[gr_EditNewProj,gr_EditNewProjCancel])
    
    def hide_new_proj():
        return gr.Button.update(visible=False),gr.Button.update(visible=False)
    
    gr_EditNewProjCancel.click(hide_new_proj,None,[gr_EditNewProj,gr_EditNewProjCancel])

    def create_new_project():
        global selected_item
        global selected_item_prompt
        global selected_item_scenetext
        global full_text
        global data_structure
        global params

        selected_item = "History 1"
        selected_item_prompt = ""
        selected_item_scenetext = ""
        full_text = ""
        data_structure = [{"outline": selected_item, "prompt": selected_item_prompt, "scenetext": selected_item_scenetext, "is_summary": False}]
        params['projectname'] = 'new_project'
        save_state()


    gr_EditNewProj.click(create_new_project,None,None).then(hide_new_proj,None,[gr_EditNewProj,gr_EditNewProjCancel]).then(full_update_ui,None,[gr_scenes_radio,gr_prompt,gr_generated_text,gr_fulltext])

    def show_proj_save():
        return gr.Textbox.update(value = params['projectname'], interactive= True, visible=True),gr.Button.update(visible=True),gr.Button.update(visible=True)

    def hide_proj_save():
        return gr.Textbox.update(visible=False),gr.Button.update(visible=False),gr.Button.update(visible=False)
    
    gr_btn_saveproject.click(show_proj_save,None,[gr_EditName,gr_EditNameSave,gr_EditNameCancel])

    gr_EditNameCancel.click(hide_proj_save,None,[gr_EditName,gr_EditNameSave,gr_EditNameCancel])

    def project_save(projname):
        global params
        params['projectname'] = projname
        projpath = save_proj_path +"/"+ projname+".json"
        save_to_json(projpath)
        save_state()

    gr_EditNameSave.click(project_save,gr_EditName,None).then(hide_proj_save,None,[gr_EditName,gr_EditNameSave,gr_EditNameCancel])

    def show_project_dropdown():
        projects = get_available_projects()
        return gr.Dropdown.update(choices=projects, value='None', visible = True),gr.Button.update(visible=True),gr.Button.update(visible=True) 
   

    gr_btn_loadproject.click(show_project_dropdown,None,[gr_projh_drop,gr_EditNameLoad,gr_EditNameLCancel])

    def hide_project_dropdown():
        return gr.Dropdown.update(visible = False),gr.Button.update(visible=False),gr.Button.update(visible=False) 

    gr_EditNameLCancel.click(hide_project_dropdown,None,[gr_projh_drop,gr_EditNameLoad,gr_EditNameLCancel])

    def load_project(projname):
        global params
        params['projectname'] = projname
        projpath = save_proj_path +"/"+ projname+".json"
        load_from_json(projpath)
        save_state()

    gr_EditNameLoad.click(load_project,gr_projh_drop,None).then(hide_project_dropdown,None,[gr_projh_drop,gr_EditNameLoad,gr_EditNameLCancel]).then(full_update_ui,None,[gr_scenes_radio,gr_prompt,gr_generated_text,gr_fulltext])

    def update_item_ui():
        global selected_item
        global selected_item_prompt
        global selected_item_scenetext
        return selected_item_prompt, selected_item_scenetext


    def update_scenes_ui():
        global selected_item
        return gr.Radio.update(choices=get_scene_list(), value=selected_item)

    def select_scene(scene_name):
        global selected_item
        global selected_item_prompt
        global selected_item_scenetext

        if does_outline_exist(scene_name):
            selected_item = scene_name
            selected_item_prompt, selected_item_scenetext = get_data_by_outline(scene_name)
        

    gr_scenes_radio.change(select_scene,gr_scenes_radio,None).then(update_item_ui,None,[gr_prompt,gr_generated_text],show_progress=False)

    #def add_new_item():
    #    add_item_auto("History","","")

    #gr_btn_addnew_scene.click(add_new_item,None,None).then(update_scenes_ui, None, gr_scenes_radio,show_progress=False).then(update_item_ui, None,[gr_prompt,gr_generated_text],show_progress=False)

    def del_cur_scene():
        global selected_item
        delete_item_by_outline(selected_item)
        return generate_combined_text_w_prompt()

    gr_btn_del_scene.click(del_cur_scene,None,gr_fulltext).then(update_scenes_ui, None, gr_scenes_radio,show_progress=False).then(update_item_ui, None,[gr_prompt,gr_generated_text],show_progress=False)

    gr_btn_del_All.click(create_new_project,None,None).then(full_update_ui,None,[gr_scenes_radio,gr_prompt,gr_generated_text,gr_fulltext])


    def change_scenetext(text):
        global selected_item
        global selected_item_scenetext
        selected_item_scenetext = text
        update_scenetext_by_outline(selected_item,selected_item_scenetext)
        return generate_combined_text_w_prompt()

    gr_generated_text.input(change_scenetext,gr_generated_text,gr_fulltext,show_progress=False)

    def moveitemup():
        global selected_item
        move_item_up(selected_item)

        return gr.Radio.update(choices=get_scene_list(), value=selected_item), generate_combined_text_w_prompt()
    
    gr_itemUp.click(moveitemup,None,[gr_scenes_radio,gr_fulltext])


    def moveitemdown():
        global selected_item
        move_item_down(selected_item)

        return gr.Radio.update(choices=get_scene_list(), value=selected_item), generate_combined_text_w_prompt()
    
    gr_itemDown.click(moveitemdown,None,[gr_scenes_radio,gr_fulltext])

    input_paramsA = [gr_prompt, gr_generated_text, shared.gradio['interface_state']]
    output_paramsA =[gr_generated_text,gr_fulltext]

    def make_sure_prompt_exist(prompt_text):
        
        if prompt_text=='' and len(data_structure)>0:
            last_item = data_structure[-1]
            prompt_text = last_item["prompt"]

        return prompt_text

    def clean_prompt(prompt):
        if params["auto_clear"]:
            return ''
        else:
            return prompt

   
    def add_new_item_generate(prompt_text):
        add_item_auto("History",prompt_text,"")

    gr_btn_generate.click(add_new_item_generate,gr_prompt,None).then(update_scenes_ui, None, gr_scenes_radio,show_progress=False).then(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        generate_reply_wrapperMY, inputs=input_paramsA, outputs= output_paramsA, show_progress=False).then(clean_prompt,gr_prompt,gr_prompt, show_progress=False)

    gr_btn_regenerate.click(make_sure_prompt_exist,gr_prompt,gr_prompt, show_progress=False).then(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        generate_reply_wrapperMY, inputs=input_paramsA, outputs= output_paramsA, show_progress=False)

    gr_btn_generate_np.click(add_new_item_generate,gr_prompt,None).then(update_scenes_ui, None, gr_scenes_radio,show_progress=False).then(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        generate_reply_wrapperMY_NP, inputs=input_paramsA, outputs= output_paramsA, show_progress=False).then(clean_prompt,gr_prompt,gr_prompt)

    gr_btn_regenerate_np.click(make_sure_prompt_exist,gr_prompt,gr_prompt, show_progress=False).then(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        generate_reply_wrapperMY_NP, inputs=input_paramsA, outputs= output_paramsA, show_progress=False)
 
    gr_btn_generate_continue_np.click(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
        partial(generate_reply_wrapperMY_NP, _continue=True), inputs=input_paramsA, outputs= output_paramsA, show_progress=False)

    gr_btn_generate_continue.click(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(
         partial(generate_reply_wrapperMY, _continue=True), inputs=input_paramsA, outputs= output_paramsA, show_progress=False)

    def stop_everything_eventMy():
        shared.stop_everything = True

    gr_btn_stop.click(stop_everything_eventMy, None, None, queue=False)    
    gr_btn_stop_np.click(stop_everything_eventMy, None, None, queue=False)


    include_last_history.change(lambda x: params.update({"include_history_nr": x}), include_last_history,None)
    gr_auto_clear.change(lambda x: params.update({"auto_clear": x}), gr_auto_clear, None)
    gr_include_history.change(lambda x: params.update({"include_history": x}), gr_include_history, None)

    gr_user_tag.change(lambda x: params.update({"user_tag": x}), gr_user_tag, None)
    gr_assistant_tag.change(lambda x: params.update({"assistant_tag": x}), gr_assistant_tag, None)

    gr_full_json.change(lambda x: params.update({"render_json": x}), gr_full_json, None)
    gr_full_systemprompt.change(lambda x: params.update({"system_prompt": x}), gr_full_systemprompt, None)
 
    gr_include_prompt.change(lambda x: params.update({"include_prompt": x}), gr_include_prompt, None)
    gr_include_response.change(lambda x: params.update({"include_response": x}), gr_include_response, None)


    def update_full():
        save_state()
        return generate_combined_text_w_prompt()

    gr_regenerate_full.click(update_full,None,gr_fulltext)

