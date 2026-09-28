from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.table(name='genieology.silver_pyspark.fct_reviews')
def fct_reviews():
    return (
        spark.read.table('genieology.bronze.review')
        .withColumn('posted_at', F.col('date').cast('timestamp'))
        .select(
            F.col('review_id'),
            F.col('business_id'),
            F.col('posted_at'),
            F.col('text').alias('review_text'),
            F.col('stars').alias('rating'),
            F.col('cool').alias('cool_count'),
            F.col('funny').alias('funny_count'),
            F.col('useful').alias('useful_count')
        )
    )