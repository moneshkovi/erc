"""Full training script"""
import argparse
import json
import logging
import os

import torch
import yaml
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          Trainer, TrainingArguments)

from utils import ErcTextDataset, compute_metrics, get_num_classes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main(
    OUTPUT_DIR: str,
    SEED: int,
    DATASET: str,
    BATCH_SIZE: int,
    model_checkpoint: str,
    roberta: str,
    speaker_mode: str,
    num_past_utterances: int,
    num_future_utterances: int,
    NUM_TRAIN_EPOCHS: int,
    WEIGHT_DECAY: float,    
    WARMUP_RATIO: float,
    **kwargs,
):
    """Perform full training with the given parameters."""

    NUM_CLASSES = get_num_classes(DATASET)

    with open(os.path.join(OUTPUT_DIR, "hp.json"), "r") as stream:
        hp_best = json.load(stream)

    LEARNING_RATE = hp_best["learning_rate"]

    logging.info(f"(LOADED) best hyper parameters: {hp_best}")

    OUTPUT_DIR = OUTPUT_DIR.replace("-seed-42", f"-seed-{SEED}")

    EVALUATION_STRATEGY = "epoch"
    LOGGING_STRATEGY = "epoch"
    SAVE_STRATEGY = "epoch"
    ROOT_DIR = "./multimodal-datasets/"

    if model_checkpoint is None:
        model_checkpoint = f"roberta-{roberta}"

    PER_DEVICE_TRAIN_BATCH_SIZE = BATCH_SIZE
    PER_DEVICE_EVAL_BATCH_SIZE = BATCH_SIZE * 2
    if torch.cuda.is_available():
        FP16 = True
    else:
        FP16 = False
    LOAD_BEST_MODEL_AT_END = True

    METRIC_FOR_BEST_MODEL = "eval_f1_weighted"
    GREATER_IS_BETTER = True

    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        evaluation_strategy=EVALUATION_STRATEGY,
        logging_strategy=LOGGING_STRATEGY,
        save_strategy=SAVE_STRATEGY,
        per_device_train_batch_size=PER_DEVICE_TRAIN_BATCH_SIZE,
        per_device_eval_batch_size=PER_DEVICE_EVAL_BATCH_SIZE,
        load_best_model_at_end=LOAD_BEST_MODEL_AT_END,
        seed=SEED,
        fp16=FP16,
        learning_rate=LEARNING_RATE,
        num_train_epochs=NUM_TRAIN_EPOCHS,
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=WARMUP_RATIO,
        metric_for_best_model=METRIC_FOR_BEST_MODEL,
        greater_is_better=GREATER_IS_BETTER,
    )

    ds_train = ErcTextDataset(
        DATASET=DATASET,
        SPLIT="train",
        speaker_mode=speaker_mode,
        num_past_utterances=num_past_utterances,
        num_future_utterances=num_future_utterances,
        model_checkpoint=model_checkpoint,
        ROOT_DIR=ROOT_DIR,
        SEED=SEED,
    )

    ds_val = ErcTextDataset(
        DATASET=DATASET,
        SPLIT="val",
        speaker_mode=speaker_mode,
        num_past_utterances=num_past_utterances,
        num_future_utterances=num_future_utterances,
        model_checkpoint=model_checkpoint,   
        ROOT_DIR=ROOT_DIR,
        SEED=SEED,
    )

    ds_test = ErcTextDataset(
        DATASET=DATASET,
        SPLIT="test",
        speaker_mode=speaker_mode,
        num_past_utterances=num_past_utterances,
        num_future_utterances=num_future_utterances,
        model_checkpoint=model_checkpoint,
        ROOT_DIR=ROOT_DIR,
        SEED=SEED,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_checkpoint, use_fast=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        model_checkpoint, num_labels=NUM_CLASSES
    )

    logging.info(f"training a full model with full data ...")

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds_train,
        eval_dataset=ds_val,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    logging.info(f"eval ...")
    val_results = trainer.evaluate()
    with open(os.path.join(OUTPUT_DIR, "val-results.json"), "w") as stream:
        json.dump(val_results, stream, indent=4)
    logging.info(f"eval results: {val_results}")

    if len(ds_test) != 0:
        logging.info(f"test ...")
        test_results = trainer.predict(ds_test)
        with open(os.path.join(OUTPUT_DIR, "test-results.json"), "w") as stream:
            json.dump(test_results.metrics, stream, indent=4)
        logging.info(f"test results: {test_results.metrics}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="erc RoBERTa text huggingface training"
    )
    parser.add_argument("--OUTPUT-DIR", type=str)
    parser.add_argument("--SEED", type=int)

    args = parser.parse_args()
    args = vars(args)

    with open("./train-erc-text.yaml", "r") as stream:
        args_ = yaml.safe_load(stream)

    for key, val in args_.items():
        args[key] = val

    logging.info(f"arguments given to {__file__}: {args}")

    main(**args)
