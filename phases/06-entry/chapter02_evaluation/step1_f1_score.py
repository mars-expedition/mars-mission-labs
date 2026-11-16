from azure.ai.evaluation import F1ScoreEvaluator

f1_score = F1ScoreEvaluator(threshold=0.5)

result = f1_score(
    response="Guiado nominal: trayectoria dentro de parámetros, sin correcciones pendientes.",
    ground_truth="Computadora de guiado: trayectoria nominal, sin correcciones pendientes.",
)
print(result)
