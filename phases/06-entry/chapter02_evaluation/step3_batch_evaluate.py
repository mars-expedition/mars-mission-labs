from azure.ai.evaluation import F1ScoreEvaluator, evaluate

result = evaluate(
    data="data.jsonl",
    evaluators={"f1_score": F1ScoreEvaluator(threshold=0.5)},
    output_path="eval_results.json",
)

print("Métricas agregadas:", result["metrics"])
print("Primera fila:", result["rows"][0])
