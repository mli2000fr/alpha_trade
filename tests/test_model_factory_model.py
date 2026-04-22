from modelFactory import model

def test_model_importable():
    assert hasattr(model, "__doc__")


def test_lstm_attention_module_uses_distinct_test_metrics() -> None:
    module = model.LSTMAttentionModule(input_size=3)

    assert module.test_acc is not module.val_acc
    assert module.test_precision is not module.val_precision
    assert module.test_recall is not module.val_recall
    assert module.test_auc is not module.val_auc


