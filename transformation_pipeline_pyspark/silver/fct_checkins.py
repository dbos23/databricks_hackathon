from pyspark import pipelines as dp
from pyspark.sql.functions import split, explode, col, count, min, max

@dp.table(name='genieology.silver_pyspark.fct_checkins')
def fct_checkins():
    exploded_df = (
        spark.read.table('genieology.bronze.checkin')
        .withColumn('checkin_date', explode(split(col('date'), ',')))
        .select(
            col('business_id'),
            col('checkin_date')
        ))
    
    final_df = (
        exploded_df
            .groupby(col('business_id'))
            .agg(
                count('business_id').alias('checkin_count'),
                min('checkin_date').alias('first_checkin'),
                max('checkin_date').alias('latest_checkin'),
            )
    )

    return final_df