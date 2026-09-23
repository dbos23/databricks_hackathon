from pyspark import pipelines as dp
from pyspark.sql.functions import col, coalesce, lit

@dp.table(name='genieology.gold_pyspark.business')
def business():
    dim_business = spark.read.table('genieology.silver_pyspark.dim_business')
    fct_checkins = spark.read.table('genieology.silver_pyspark.fct_checkins')
    
    return (
        dim_business.join(fct_checkins, how='left', on='business_id')
        .select(
            col('dim_business.business_id'),
            col('dim_business.business_name'),
            col('dim_business.subcategories'),
            col('dim_business.city'),
            col('dim_business.state'),
            col('dim_business.address'),
            col('dim_business.postal_code'),
            col('dim_business.latitude'),
            col('dim_business.longitude'),
            col('dim_business.review_count'),
            col('dim_business.rating'),
            coalesce(col('fct_checkins.checkin_count'), lit(0)).alias('checkin_count'),
            col('fct_checkins.first_checkin'),
            col('fct_checkins.latest_checkin')
        )
    )