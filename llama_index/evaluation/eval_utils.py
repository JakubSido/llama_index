"""Get evaluation utils.

NOTE: These are beta functions, might change.

"""

import asyncio
import os
from collections import defaultdict
from typing import Any, List, Optional

import numpy as np
import pandas as pd

from llama_index.evaluation.base import EvaluationResult
from llama_index.indices.query.base import BaseQueryEngine
from llama_index.ingestion.client import ProjectCreate
from llama_index.ingestion.client.client import PlatformApi
from llama_index.ingestion.client.types.eval_question_create import EvalQuestionCreate
from llama_index.ingestion.pipeline import (
    DEFAULT_BASE_URL,
    DEFAULT_PROJECT_NAME,
)


def asyncio_module(show_progress: bool = False) -> Any:
    if show_progress:
        from tqdm.asyncio import tqdm_asyncio

        module = tqdm_asyncio
    else:
        module = asyncio

    return module


async def aget_responses(
    questions: List[str], query_engine: BaseQueryEngine, show_progress: bool = False
) -> List[str]:
    """Get responses."""
    tasks = []
    for question in questions:
        tasks.append(query_engine.aquery(question))
    asyncio_mod = asyncio_module(show_progress=show_progress)
    return await asyncio_mod.gather(*tasks)


def get_responses(
    *args: Any,
    **kwargs: Any,
) -> List[str]:
    """Get responses.

    Sync version of aget_responses.

    """
    return asyncio.run(aget_responses(*args, **kwargs))


def get_results_df(
    eval_results_list: List[EvaluationResult], names: List[str], metric_keys: List[str]
) -> pd.DataFrame:
    """Get results df.

    Args:
        eval_results_list (List[EvaluationResult]):
            List of evaluation results.
        names (List[str]):
            Names of the evaluation results.
        metric_keys (List[str]):
            List of metric keys to get.

    """
    metric_dict = defaultdict(list)
    metric_dict["names"] = names
    for metric_key in metric_keys:
        for eval_results in eval_results_list:
            mean_score = np.array([r.score for r in eval_results[metric_key]]).mean()
            metric_dict[metric_key].append(mean_score)
    return pd.DataFrame(metric_dict)


def upload_eval_dataset(
    dataset_name: str,
    questions: List[str],
    project_name: str = DEFAULT_PROJECT_NAME,
    platform_base_url: Optional[str] = None,
    platform_api_key: Optional[str] = None,
) -> None:
    """Upload questions to platform dataset."""
    platform_base_url = platform_base_url or os.environ.get(
        "PLATFORM_BASE_URL", DEFAULT_BASE_URL
    )
    platform_api_key = platform_api_key or os.environ.get("PLATFORM_API_KEY", None)

    client = PlatformApi(base_url=platform_base_url, token=platform_api_key)

    project = client.project.upsert_project(request=ProjectCreate(name=project_name))
    assert project.id is not None

    eval_dataset = client.project.create_eval_dataset_for_project(
        project_id=project.id, name=dataset_name
    )
    assert eval_dataset.id is not None

    eval_questions = client.eval.create_questions(
        dataset_id=eval_dataset.id,
        request=[EvalQuestionCreate(content=q) for q in questions],
    )

    assert len(eval_questions) == len(questions)
    print(f"Uploaded {len(questions)} questions to dataset {dataset_name}")
