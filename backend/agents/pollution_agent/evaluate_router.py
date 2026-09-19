import os
import sys

# Need to import our router
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.agents.pollution_agent.router import is_pollution_question

train_set = [
    # 30 messages for tuning (15 pollution, 15 other/mixed)
    ("What is the AQI today?", "pollution"),
    ("Is there smog in the city?", "pollution"),
    ("My breath is choking, is the air bad?", "pollution"),
    ("pradushan kaisa hai", "pollution"),
    ("hyderabad vayu gunvatta", "pollution"),
    ("gali kalushyam yela undi", "pollution"),
    ("what is the pm2.5 level", "pollution"),
    ("is it safe to go out today air quality", "pollution"),
    ("any dust storms?", "pollution"),
    ("haze in the morning", "pollution"),
    ("what are the NO2 emissions", "pollution"),
    ("प्रदूषण का स्तर क्या है?", "pollution"),
    ("గాలి నాణ్యత", "pollution"),
    ("is the air clean", "pollution"),
    ("show me the aqi summary", "pollution"),
    
    ("how is the traffic jam", "not"),
    ("is there any power outage", "not"),
    ("will it rain today", "not"),
    ("traffic emissions", "mixed"),
    ("rain and pollution", "mixed"),
    ("baarish ho rahi hai", "not"),
    ("bijli kab aayegi", "not"),
    ("varsham paduthunda", "not"),
    ("signal green time", "not"),
    ("can you show the heat wave alert", "not"),
    ("how much solar energy is produced", "not"),
    ("flood in hyderabad", "not"),
    ("are there any diversions", "not"),
    ("what is the power load", "not"),
    ("cyclone warning", "not"),
]

test_set = [
    # 20 messages for testing (10 pollution, 10 other/mixed)
    ("give me the 7 day pollution forecast", "pollution"),
    ("hawa kharaab hai kya", "pollution"),
    ("dhool bahot hai", "pollution"),
    ("is ozone high today", "pollution"),
    ("what is the dominant pollutant", "pollution"),
    ("are there any air quality alerts", "pollution"),
    ("dummu ekkuvaga undi", "pollution"),
    ("what are the pm10 levels", "pollution"),
    ("is the air safe for sensitive groups", "pollution"),
    ("वायु गुणवत्ता कैसी है", "pollution"),
    
    ("heavy traffic on ring road", "not"),
    ("is the grid stable", "not"),
    ("what is the temperature", "not"),
    ("traffic congestion and smog", "mixed"),
    ("power blackout", "not"),
    ("weather forecast", "not"),
    ("parking availability", "not"),
    ("dhua from accident", "mixed"),
    ("solar generation", "not"),
    ("humidity levels", "not")
]

def evaluate(dataset, name):
    print(f"--- Evaluating {name} set ---")
    correct = 0
    true_pos = 0
    false_pos = 0
    false_neg = 0
    
    for text, true_label in dataset:
        pred = is_pollution_question(text)
        print(f"Text: '{text}' | True: {true_label} | Pred: {pred}")
        if pred == true_label:
            correct += 1
            if true_label in ["pollution", "mixed"]:
                true_pos += 1
        else:
            if pred in ["pollution", "mixed"] and true_label == "not":
                false_pos += 1
            elif pred == "not" and true_label in ["pollution", "mixed"]:
                false_neg += 1
            # "mixed" vs "pollution" mismatch? We consider precision/recall on identifying pollution relevance
            if true_label in ["pollution", "mixed"]:
                if pred == "not":
                    pass # already counted false_neg
                else:
                    # If true is mixed, and pred is pollution, it's a partial success but let's count as true_pos for relevance
                    true_pos += 1
            else:
                if pred in ["pollution", "mixed"]:
                    pass # already counted false_pos
                
    accuracy = correct / len(dataset)
    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) > 0 else 0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) > 0 else 0
    
    print(f"Accuracy: {accuracy:.2f}")
    print(f"Precision (Pollution/Mixed): {precision:.2f}")
    print(f"Recall (Pollution/Mixed): {recall:.2f}\n")
    return accuracy, precision, recall

evaluate(train_set, "Train (Tuning)")
evaluate(test_set, "Test (Held-out)")
