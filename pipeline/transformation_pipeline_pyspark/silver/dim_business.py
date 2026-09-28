from pyspark import pipelines as dp
from pyspark.sql.functions import col

@dp.table(name='genieology.silver_pyspark.dim_business')
def dim_business():
    business_bronze = spark.read.table('genieology.bronze.business')
    metro_areas = spark.read.table('genieology.bronze.metro_areas')
    
    return (
        business_bronze.join(metro_areas, how='inner', on='business_id')
        .select(
            col('business.business_id'),
            col('name').alias('business_name'),
            col('categories').alias('subcategories'),
            col('city'),
            col('state'),
            col('address'),
            col('postal_code'),
            col('latitude'),
            col('longitude'),
            col('review_count'),
            col('stars').alias('rating'),
        )
        .filter(col('is_open') == 1)
        .filter(col('metro_area') == 'New Orleans')
    )