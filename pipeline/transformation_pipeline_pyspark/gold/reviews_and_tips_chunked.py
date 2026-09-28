from pyspark import pipelines as dp
from pyspark.sql import functions as F

chunk_size = 150
chunk_overlap = 20
step = chunk_size - chunk_overlap

@dp.table(name="genieology.gold_pyspark.reviews_and_tips_chunked")
def reviews_and_tips_chunked():
    text_len = F.length('full_text')

    # keep going until a chunk reaches the end of the text
    num_chunks = (
        F.when(text_len <= chunk_size, F.lit(1))
         .otherwise(F.ceil((text_len - chunk_size) / step) + 1)
         .cast('int')
    )

    return (
        spark.read.table('genieology.gold_pyspark.reviews_and_tips')
        .filter(F.col('full_text').isNotNull() & (text_len > 0))
        .withColumn('chunk_id', F.explode(F.sequence(F.lit(0), num_chunks - 1)))
        .withColumn('text_chunk', F.col('full_text').substr(F.col('chunk_id') * step + 1, F.lit(chunk_size)))
        .select(
            F.col('text_id'),
            F.col('chunk_id'),
            F.md5(F.concat_ws('|', F.col('text_id'), F.col('chunk_id'))).alias('pk'),
            F.col('text_chunk')
            )
    )
