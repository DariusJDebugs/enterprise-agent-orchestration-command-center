from app.embeddings import HashEmbeddingModel


def test_embeddings_are_deterministic_and_normalized():
    model = HashEmbeddingModel(96)
    first = model.embed("security incident response and disaster recovery")
    second = model.embed("security incident response and disaster recovery")
    assert first == second
    norm = sum(value * value for value in first) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_related_text_scores_above_unrelated_text():
    model = HashEmbeddingModel(192)
    query = model.embed("vendor security incident notification")
    related = model.embed("supplier breach notification and security incident response")
    unrelated = model.embed("cafeteria menu and office furniture colors")
    assert model.cosine_similarity(query, related) > model.cosine_similarity(query, unrelated)
