import csv
import json
from tqdm import tqdm
import numpy as np
from prettytable import PrettyTable
import os
import time
import openai
from openai import OpenAI

api_key = ""

openai.api_key = api_key

client = OpenAI(
    api_key = api_key
)

models = client.models.list()

for model in models.data:
    # if model.id.startswith("gpt-"):
    print(model.id)

# input_file_name = "autohallusion_data_gemini_res.json"
# output_file_name = "autohallusion_data_gemini_res_evaluated.json"
# input_file_name = "autohallusion_data_gpt_res.json"
# output_file_name = "autohallusion_data_gpt_res_evaluated.json"
# input_file_name = "autohallusion_data_claude_res.json"
# output_file_name = "autohallusion_data_claude_res_evaluated.json"

# input_file_name = "autohallusion_data_llava_res.json"
# output_file_name = "autohallusion_data_llava_res_evaluated.json"

input_file_name = "/home/mali2/POVID/autohal_povid_spatial.json"
output_file_name = "autohallusion_data_minigpt4_res_evaluated_spat.json"

def evaluate_by_chatgpt(data, save_json_path, output_entry="res", correctness_entry="correctness", gpt_model="gpt-4o", load_json=True):
    if load_json and os.path.exists(save_json_path):
        with open(save_json_path, 'r') as f:
            output = json.load(f)
    else:
        output = []

    for sample in tqdm(data[len(output):]):
        prompt = 'Imagine you are an intelligent teacher. Thoroughly read the question, reference answer and the prediction answer to ensure a clear understanding of the information provided. Assess the correctness of the predictions. '
        prompt += 'If the prediction answer does not conflict with the reference answer, please generate “correct”. If the prediction answer conflict with the reference answer, please generate “incorrect”. The output should only be “correct” or “incorrect”. \n\n Question:'
        prompt += sample['prompt']
        prompt += '\nReference answer: '
        prompt += sample['ground_truth']
        prompt += '\nPrediction answer:'
        prompt += sample[output_entry]
        prompt += '\nOutput:'

        # https://github.com/openai/openai-python/issues/322#issuecomment-1767841683

        client = OpenAI(api_key=api_key)

        while True:
            try:
                response = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                break
            except:
                print("GPT4V Timeout, retrying... Q: {}".format(prompt))
                time.sleep(5)  # Wait for 5 seconds before retrying

        output_text = response.choices[0].message.content

        if 'incorrect' in output_text.lower(): 
            gpt_correctness = False

        elif 'correct' in output_text.lower():
            gpt_correctness = True
        else:
            gpt_correctness = False

        sample[correctness_entry] = gpt_correctness

        output.append(sample)

        with open(save_json_path, 'w') as f:
            json.dump(output, f)

    return output


def get_percentage(data, model_correctness_entry): # per question

    correct = 0
    total = 0

    # Breakdowns
    correct_syn = 0
    total_syn = 0

    correct_real = 0
    total_real = 0

    for r in data:
        total += 1

        img_key = "image_name"

        # Determine synthetic / real-world
        if "_set_syn" in str(r[img_key]):
            total_syn += 1
        else:
            total_real += 1

        if r[model_correctness_entry]:
            correct += 1
            # Determine synthetic / real-world
            if "_set_syn" in str(r[img_key]):
                correct_syn += 1
            else:
                correct_real += 1

    return (correct, correct_syn, correct_real,
            total, total_syn, total_real)


if __name__ == "__main__":

    with open(input_file_name, 'r') as file:
        data = json.load(file)
        print(input_file_name)

    data = evaluate_by_chatgpt(data, output_file_name, output_entry="response", correctness_entry="correctness", gpt_model="gpt-4o", load_json=True)

    (correct, correct_syn, correct_real,
     total, total_syn, total_real) = (
        get_percentage(data, model_correctness_entry="correctness"))

    print("Overall Accuracy:" + str(round(100 * correct / total, 4)))

    print("Overall Synthetic Accuracy:" + str(round(100 * correct_syn / total_syn, 4)))

    print("Overall Real-World Accuracy:" + str(round(100 * correct_real / total_real, 4)))
