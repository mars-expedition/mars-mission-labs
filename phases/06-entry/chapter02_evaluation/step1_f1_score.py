from azure.ai.evaluation import F1ScoreEvaluator

f1_score = F1ScoreEvaluator(threshold=0.5)

result = f1_score(
    response="Propulsión nominal: tanques al 82%, motores principales en estado nominal.",
    ground_truth="Tanques al 82%, motores principales nominales.",
)
print(result)
