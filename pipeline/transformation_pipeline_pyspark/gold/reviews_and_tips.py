from pyspark import pipelines as dp
from pyspark.sql.functions import col, lit, concat

@dp.table(name='genieology.gold_pyspark.reviews_and_tips')
def reviews_and_tips():
    business = spark.read.table('genieology.gold_pyspark.business')
    fct_reviews = spark.read.table('genieology.silver_pyspark.fct_reviews')
    fct_tips = spark.read.table('genieology.silver_pyspark.fct_tips')
    
    reviews_df = (
        fct_reviews.join(business, how='inner', on='business_id')
        .withColumn('type', lit('review'))
        .withColumn('full_text', concat(col('fct_reviews.rating').cast('string'), lit('/5 stars. '), col('review_text')))
        .select(
            col('review_id').alias('text_id'),
            col('fct_reviews.business_id'),
            col('type'),
            col('posted_at'),
            col('full_text')
        )
    )

    tips_df = (
        fct_tips.join(business, how='inner', on='business_id')
        .withColumn('type', lit('tip'))
        .select(
            col('tip_id').cast('string').alias('text_id'),
            col('fct_tips.business_id'),
            col('type'),
            col('posted_at'),
            col('tip_text').alias('full_text')
        )
    )

    return reviews_df.union(tips_df)