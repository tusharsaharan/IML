"""Module 12: Semantic similarity + Hinglish→English gloss.

Embeddings are the one part of the "vectors + translation" ask that the
research genuinely needs: BLEU/ROUGE-L measure word overlap, which scores a
correct English paraphrase of a Hinglish query near zero. Translation to
English as a *mandatory pipeline stage* is deliberately NOT done here — it
would erase the code-mixed phenomenon under study and add a paid hop in
front of the compressor. Translation exists only as an optional,
honestly-labelled baseline/verification aid.
"""
