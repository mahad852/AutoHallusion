# hsy 2024.05.11 clean utils for gemini
# setup
import google.generativeai as genai
import os
from api_key_gemini import GEMINI_API_KEY
from PIL import Image
import time
import numpy as np
import shutil
import random
from utils.utils_eval import evaluate_by_chatgpt_quick_test
from utils.utils import correlated_object_segment, correlated_img_generate

########### common utils
# Extract the single object from the scene with masks
def single_obj_extract(img_path, mask_bbox, idx, save_prefix):
    raw_img = Image.open(img_path)
    bbox = mask_bbox[idx]
    obj_img = np.array(raw_img)[bbox[1]:bbox[3], bbox[0]:bbox[2], :]
    obj_img = Image.fromarray(obj_img.astype(np.uint8)).convert('RGBA')
    obj_img.save(os.path.join(save_prefix, "obj_" + str(idx) + ".png"))
    return obj_img

def safe_remove_dir(path, retries=5, delay=3):
    """Attempt to remove a directory with retries for stubborn files like .nfs files on NFS mounts."""
    for attempt in range(retries):
        try:
            # Try to remove the directory with all its contents
            shutil.rmtree(path)
            print(f"Successfully removed directory: {path}")
            break
        except OSError as e:
            print(f"Attempt {attempt + 1} failed with error: {e}")
            time.sleep(delay)  # Wait before trying again
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break
    else:
        # Final attempt to list remaining files if any
        remaining_files = os.listdir(path)
        if remaining_files:
            print(f"Failed to remove all files, remaining: {remaining_files}")
        else:
            print(f"Directory already empty and will now be removed.")
            os.rmdir(path)  # Final removal if somehow it's empty now

def close_logger(logger):
    """Closes all handlers of the logger to free up resources."""
    handlers = logger.handlers[:]
    for handler in handlers:
        handler.close()
        logger.removeHandler(handler)


############ Related to Gemini
#print(GEMINI_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# for m in genai.list_models():
#     print(m.name)
#     print(m.supported_generation_methods)

def debug():
    model = genai.GenerativeModel('gemini-pro-vision')
    model1 = genai.GenerativeModel('gemini-pro')


    image_path = './test2.jpg'  # Replace with the path to your image
    img = Image.open(image_path)

    response = model.generate_content(["Tell me about the image?", img])
    #response = model1.generate_content(["Generate an image of sunrise?"])
    #response = model1.generate_content(["How to use microwave?"])

    print(response.text)
    #print(response.image)

    return 

# Easy QA function to interact with gemini
# gemini temp ranges [0,1]
def qa_gemini(question, temp=0.75):
    client = genai.GenerativeModel('gemini-pro')

    question += "Keep the outcome within 200 words."

    generation_config = genai.GenerationConfig(   
        temperature=temp,
        )

    while True:
        try:
            #response = client.generate_content([question])
            response = client.generate_content(
                contents = question,
                generation_config=generation_config,
                )

            break
        except:
            print("Gemini Timeout qa_gemini, retrying... Q: {}".format(question))
            time.sleep(5)  # Wait for 5 seconds before retrying

    answer = response.text

    print('qa_gemini question {}'.format(question))
    print('qa_gemini answer {}'.format(answer))

    return answer

# Ask Gemini with questions and images, get answers
# Input: Masked image path
# Output: Object name
def vqa_gemini(masked_image_path, questions, temp=0.5, max_try=5):
    counter = 0
    generation_config = genai.GenerationConfig(   
        temperature=temp,
        max_output_tokens=300,
        )

    while True:
        try:
            model = genai.GenerativeModel('gemini-pro-vision')

            img = Image.open(masked_image_path)

            #response = model.generate_content([questions, img])
            response = model.generate_content(
                contents = [questions, img],
                generation_config=generation_config,)

            answer = response.text
            break
        except:
            counter += 1
            print("vqa_gemini image query timeout,  try {} / {}...".format(str(counter), str(max_try)))
            if counter > max_try:
                raise Exception("generate_image reaches max attempt of {}, regenerate case".format(str(max_try)))
            time.sleep(5)  # Wait for 5 seconds before retrying

    print('vqa_gemini question {}'.format(questions))

    print('vqa_gemini masked_image_path {}'.format(masked_image_path))

    print('vqa_gemini answer {}'.format(answer))

    return answer

# General image caption function, create a caption with image provided
# Input: Masked image path
# Output: Object name
def image_caption_gemini(input_img_path):
    msg = "Describe what you see in this image."
    caption = vqa_gemini(input_img_path, msg)
    print('image_caption_gemini done')
    return caption


# Think about a scenario
# Input: Masked image path
# Output: Object name
# TODO: temperature not used for now
# def scene_thinking_gemini(constraint, temperature):
#     msg = "Randomly think about a generic scene or place that can use a noun or phrase to describe. Only generate a single word or a short phrase."
#     # msg = "Randomly think about a generic scene or place that can use a one or two words to describe."
#     if constraint is not None:
#         msg += "Constraint: "
#         msg += constraint
#     scene_name = qa_gemini(msg, temperature)
#     return scene_name


def generate_noun_given_scene_gemini(num, scene, examples=None, temperature=0):

    if examples is None:
        example_prompt = ""
        example_prompt2 = ""
    else:
        example_prompt = "like {}, all ".format(",".join(examples))
        example_prompt2 = "Do not generate the same items as the ones mentioned in the example."

    prompt = '''
    Generate {} words that are noun representing different physical objects and identities that are the most likely to exist in the scene of {} ({}with very high similarity score){}

    Output format should be the list of nouns separated by comma. The output should be 
    a string with {} words and comma only.
    '''.format(num, scene, example_prompt, example_prompt2, num)

  
    model = genai.GenerativeModel('gemini-pro')

    while True:
        try:
            completion = model.generate_content([prompt])
            break
        except:
            print("Gemini Timeout generate_noun_given_scene_gemini, retrying...")
            time.sleep(5)  # Wait for 5 seconds before retrying

    words = completion.text

    print('generate_noun_given_scene_gemini: prompt: {}'.format(prompt))
    print('gemini answer: {}'.format(words))

    word_lst = words.split(",")
    word_lst = [w.strip() for w in word_lst]

    assert len(word_lst) == num

    print('output word_lst: {}'.format(word_lst))

    return word_lst, None


# not sure whether it is used
def random_obj_thinking_gemini(scene_name, temperature, cond=""):
    print('random_obj_thinking_gemini:')

    if scene_name is None:
        scene_desc = '''
                Think about one random object. Use a one or two words to describe this object.
                '''
    else:
        scene_desc = '''
                Think about one random object that is unlikely to exist in the {}. Use a one or two words to describe this object.
                '''.format(scene_name)

    obj_name = qa_gemini(scene_desc + cond, temperature)
    return obj_name


# # Find an irrelevant object given the scene and the existing objects
# # Input: Masked image path
# # Output: Object name
def irrelevant_obj_thinking_gemini(scene_name, word_list, category, temperature, cond=""):
    print('irrelevant_obj_thinking_gemini:')
    words = ",".join(word_list)
    if category is not None:
        scene_desc = '''
                Think about one commonly seen physical object from the category of {} that is irrelevant to the existing physical objects: "{}" and is unlikely to exist in the {}. Use a one or two words to describe this object.
                This object should not be a concept or too abstract. For example, Ocean, or Space is too abstract to describe by a concrete identity, while fish and space ship are good examples under those concepts.
                '''.format(category, words, scene_name)
    else:
        scene_desc = '''
                Think about one commonly seen physical object that is irrelevant to the existing physical objects: "{}" and is unlikely to exist in the {}. Use a one or two words to describe this object.
                This object should not be a concept or too abstract. For example, Ocean, or Space is too abstract to describe by a concrete identity, while fish and space ship are good examples under those concepts.
                '''.format(words, scene_name)
    obj_name = qa_gemini(scene_desc + cond, temperature)

    print('irrelevant_obj_thinking_gemini done')

    return obj_name

# Given the image of the object, generate its name and describe using no more than 3 words
def single_obj_naming_gemini(single_obj_img_path):
    msg = "Describe the object in this image with no more than 3 words. Do not add any comma or period."
    object_name = vqa_gemini(single_obj_img_path, msg)
    print('single_obj_naming_gemini done.')
    return object_name


# Given the image of the object and its name, use 1 around-10-word sentence to describe this object
def single_obj_caption_gemini(single_obj_img_path, single_obj_name):
    prompt = "Given the image of {}, describe this object using a single sentence within 10 words.".format(single_obj_name)
    answer = vqa_gemini(single_obj_img_path, prompt)
    print('single_obj_caption_gemini done.')
    return answer

# General image caption function, create a caption with image provided
# Input: Masked image path
# Output: Object name
def object_image_caption_gemini(input_img_path, obj_name, irrelevant_obj_attribute):
    attribute_category_str = ""
    attribute_category_list = list(irrelevant_obj_attribute.keys())

    for attribute_category in attribute_category_list:
        attribute_category_str += attribute_category + ", "
    msg = "Describe the {} in this image with a single paragraph. Focus on the following attributes: {}".format(obj_name, attribute_category_str)
    caption = vqa_gemini(input_img_path, msg)
    print('object_image_caption_gemini done')
    return caption

# Generate the ground truth of the image after editing
# Content: Scene (Given), Object name and description one-by-one, Background, Added Object
def gt_generation_gemini(init_img_path, mask_bbox, scene_name, irrelevant_obj, irrelevant_obj_attribute, save_prefix="./"):
    obj_img = []
    obj_name = []
    obj_description = []
    for i in range(len(mask_bbox)):
        obj_img.append(single_obj_extract(init_img_path, mask_bbox, i, save_prefix))
        obj_temp = single_obj_naming_gemini(os.path.join(save_prefix, "obj_" + str(i) + ".png"))
        obj_name.append(obj_temp)
        obj_description.append(single_obj_caption_gemini(os.path.join(save_prefix, "obj_" + str(i) + ".png"), obj_temp))

    # background_extract(init_img_path, mask_bbox, save_prefix)

    irrelevant_obj_description = object_image_caption_gemini(os.path.join(save_prefix, "pure_obj.png"),
                                                            irrelevant_obj, irrelevant_obj_attribute)

    ground_truth = {
        "scene": scene_name,
        # "background": background_caption_gpt4v(os.path.join(save_prefix, "background.png"), scene_name),
        "object_name": obj_name,
        "object_description": obj_description,
        "irrelevant_object_name": irrelevant_obj,
        "irrelevant_obj_attribute": irrelevant_obj_attribute,
        "irrelevant_object_description": irrelevant_obj_description
    }
    return ground_truth

# Generate the ground truth of the image before object removal editing
# Content: Scene (Given), Object name and description one-by-one, Removed Object and description
# Output: Ground truth, target/removed/preserved object index (For image editing and spatial relation)
def gt_generation_multi_obj_removal_gemini(init_img_path, mask_bbox, scene_name, target_obj, save_prefix="./"):
    obj_img = []
    obj_name = []
    obj_description = []
    for i in range(len(mask_bbox)):
        obj_img.append(single_obj_extract(init_img_path, mask_bbox, i, save_prefix))
        obj_temp = single_obj_naming_gemini(os.path.join(save_prefix, "obj_" + str(i) + ".png"))
        obj_name.append(obj_temp)
        obj_description.append(single_obj_caption_gemini(os.path.join(save_prefix, "obj_" + str(i) + ".png"), obj_temp))

    target_obj_description = object_image_caption_gemini(os.path.join(save_prefix, "target_obj.png"), target_obj, {})

    ground_truth = {
        "scene": scene_name,
        "object_name": obj_name,
        "object_description": obj_description,
        "non_exist_target_object_name": target_obj,
        "non_exist_target_object_description": target_obj_description
    }
    return ground_truth

def filter_remove_obj_under_scene_gemini(scene_name, irrelevant_obj_dict_lst, temperature=0.75):
    objs_prompt = ""
    for i, o in enumerate(irrelevant_obj_dict_lst):
        objs_prompt += "{}. {};".format(str(i), o["obj_name"])

    prompt = '''
        Given a list of objects, pick all objects that are relevant and related to the scene {}, or it is common to see those objects in this scene of {}.
        Each object is given an index, and return the number index only separated by comma. 
        The AutoHallusion output should only consists of numbers and comma. The list of objects are as follows: {}
    '''.format(scene_name, scene_name, objs_prompt)

    filtered_objs_idx = qa_gemini(prompt, temperature)

    obj_idx_rev = filtered_objs_idx.split(",")

    obj_idx_rev = [int(i.strip()) for i in obj_idx_rev]

    obj_idx = []
    for i in range(len(irrelevant_obj_dict_lst)):
        if i not in obj_idx_rev:
            obj_idx.append(i)

    ret_dict_lst = []

    for idx in obj_idx:
        if idx >= 0 and idx < len(irrelevant_obj_dict_lst):
            ret_dict_lst.append(irrelevant_obj_dict_lst[idx])
        else:
            print("invalid index {} in filter_remove_obj_under_scene_gemini from gemini.".format(str(idx)))

    return ret_dict_lst


def filter_most_irrelevant_gemini(scene_name, word_lst, irrelevant_obj_dict_lst, temperature=0):
    objs_prompt = ""
    for i, o in enumerate(irrelevant_obj_dict_lst):
        objs_prompt += "{}. {};".format(str(i), o["obj_name"])

    if isinstance(word_lst, str):
        words = word_lst
    elif isinstance(word_lst, list):
        words = ", ".join(word_lst)
    else:
        words = word_lst

    prompt = '''
        Given a list of objects, pick the most irrelevant object that is the most irrelevant and non-related to the scene {} and objects like {}, or it is extremely uncommon to see such object in this scene of {}.
        Each object is given an index, and return a single index number only. 
        The AutoHallusion output should only consists of a single number. The list of objects are as follows: {}
    '''.format(scene_name, words, scene_name, objs_prompt)

    filtered_obj_idx = qa_gemini(prompt, temperature)

    obj_idx = int(filtered_obj_idx.strip())

    if obj_idx >= 0 and obj_idx < len(irrelevant_obj_dict_lst):
        return irrelevant_obj_dict_lst[obj_idx]
    else:
        filtered_obj_idx = list([val for val in filtered_obj_idx if val.isnumeric()])
        obj_idx = int(filtered_obj_idx)
        if obj_idx >= 0 and obj_idx < len(irrelevant_obj_dict_lst):
            return irrelevant_obj_dict_lst[obj_idx]
        else:
            print("invalid index {} in filter_most_irrelevant_gpt4v from gpt.".format(filtered_obj_idx))
            return random.choice(irrelevant_obj_dict_lst)

def list_objects_given_img_gemini(img_path, num_list_obj):
    prompt = "List {} physical objects in the given image. The output should be a list contains object names separated by commas.".format(
        str(num_list_obj))

    out_list = []
    while len(out_list) != num_list_obj:
        answer = vqa_gemini(img_path, prompt)
        out_list = answer.split(",")

    final_list = []
    for i in range(len(out_list)):
        temp = list([val for val in out_list[i] if val.isalpha() or val.isnumeric() or val == " "])
        final_list.append("".join(temp).lower())
    return final_list

# Brutally think about two closely related objects without any other constraints
def correlated_obj_thinking_gemini(temperature=0.75, cond=""):
    prompt = """
    Can you generate two objects that are strongly correlated? If one thing appears, it often appears with the other 
    objects. For example, [fish tank, fish]. Please only generate two objects separated with commas.
    """

    answer = qa_gemini(prompt + cond, temp=temperature)
    answer = answer.replace("[", "").replace("]", "")

    out_list = answer.split(",")

    final_list = []
    for i in range(len(out_list)):
        temp = list([val for val in out_list[i] if val.isalpha() or val.isnumeric() or val == " "])
        final_list.append("".join(temp).lower())
    return final_list

# Validate code (advanced): See if the generate image only contain the target object and not disturbing obj
def correlated_img_validate_advanced_gemini(img_path, target_obj, disturbing_obj):
    question = "Does this image contain {} and not contain {}?".format(target_obj, disturbing_obj)
    pred_answer = vqa_gemini(img_path, question)
    gt = "This image contains {} and does not contain {}.".format(target_obj, disturbing_obj)

    eval_result = evaluate_by_chatgpt_quick_test(question, pred_answer, gt)

    if eval_result == "0" or eval_result == "2":
        return False
    else:
        return True


# Validate code: See if the generate image only contain the target object and not disturbing obj
def correlated_img_validate_gemini(img_path, target_obj, disturbing_obj):
    question = "Does this image contain {} and not contain {}? Only answer with yes or no.".format(target_obj,
                                                                                                   disturbing_obj)
    pred_answer = vqa_gemini(img_path, question)

    if "yes" in pred_answer.lower():
        return True
    else:
        return False


def correlated_example_create_gemini(correlated_obj, attribute_category_list, save_prefix, advanced=False):
    success_flag = False
    target_obj = None
    disturbing_obj = None

    target_attributes, disturbing_attributes = {}, {}

    while not success_flag:
        for i in range(len(correlated_obj)):
            if i == 0:
                not_i = 1
            else:
                not_i = 0

            raw_obj_path = save_prefix + "raw_" + correlated_obj[i] + ".png"
            target_attributes, disturbing_attributes = \
                correlated_img_generate([correlated_obj[i], correlated_obj[not_i]], attribute_category_list,
                                        raw_obj_path)
            correlated_object_segment(raw_obj_path, correlated_obj[i], save_prefix)

            img_path = save_prefix + "extracted_" + correlated_obj[i] + ".png"
            if advanced:
                valid_result = correlated_img_validate_advanced_gemini(img_path, correlated_obj[i], correlated_obj[not_i])
            else:
                valid_result = correlated_img_validate_gemini(img_path, correlated_obj[i], correlated_obj[not_i])

            if valid_result:
                disturbing_obj = correlated_obj[not_i]
                target_obj = correlated_obj[i]
                success_flag = True
                break

        if success_flag:
            break

    input_path = save_prefix + "raw_" + target_obj + ".png"
    img = Image.open(input_path).convert("RGBA")
    img.save(save_prefix + "obj.png")

    input_path = save_prefix + "extracted_" + target_obj + ".png"
    img = Image.open(input_path).convert("RGBA")
    img.save(save_prefix + "pure_obj.png")
    return target_obj, disturbing_obj, target_attributes, disturbing_attributes

if __name__ == "__main__":
    #generate_noun_given_scene_gemini(num=5, scene='snow', examples=None)
    debug()
    #qa_gemini('what is AI?')

    #vqa_gemini('./test2.jpg', 'describe the image')