from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window

@dp.table(name='genieology.silver_pyspark.fct_tips')
def fct_tips():
    return (
        spark.read.table('genieology.bronze.tip')
        .withColumn('posted_at', F.col('date').cast('timestamp'))
        .withColumn('tip_id', F.row_number().over(Window.orderBy(F.col('business_id'))))
        .select(
            F.col('tip_id'),
            F.col('business_id'),
            F.col('posted_at'),
            F.col('text').alias('tip_text'),
            F.col('compliment_count').alias('tip_compliment_count'),
        )
    )