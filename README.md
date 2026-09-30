# Databricks Hackathon
This repository stores all the code for the team Genieology in The Information Lab's Databricks Hackathon. The hackathon is primarily focused on AI and BI. The members of Genieology are @sitapawar (responsible for the Overview App), @jacob-aronson-data (responsible for the Business Analyst App), and @dbos23 (responsible for the data engineering pipeline and Genie Agent).

# Project Overview
We used the [Yelp open dataset](https://business.yelp.com/data/resources/open-dataset/) for our project. The premise is that Blanche Lifestyle Magazine (a fictional magazine based in New Orleans) is considering using Databricks and the paid Yelp API to better be able to write informed articles for their readers. This project is intended as a proof of concept of the value of both the data and of the functionality of Databricks.

Our project comprised the following components:
- Data engineering pipeline
- Two Databricks apps written in Python and JavaScript respectively
- Genie agent

## Data Engineering Pipeline
The data consisted of five JSON files and [one CSV file](https://www.kaggle.com/datasets/scott31/yelp-dataset-metro-areas). Our pipeline turned those files into analysis-ready tables through the following process:
1. Loaded the JSON files into an Amazon S3 bucket
2. Ingested those files into Databricks tables using the native Databricks S3 connector
3. Transformed the raw data according to the medallion architecture using a Spark Declarative Pipeline. This was initially done with SQL. In the spirit of the hackathon's core purpose — advancing our own learning — this was then replicated using PySpark

## Overview App
This is an interactive dashboard coded in Python and deployed as a Databricks app. Its intended purpose is to give a broad overview of the data and help its users to narrow down their search for the best businesses in New Orleans for their needs. It was created with adherence to a style guide that was also used in the other app and the Genie Agent.

For more information about the Overview App see [README](./overview_app/README.md).

## Business Analyst App
Similar to the Overview app, the Business Analyst app is a dashboard deployed as a Databricks app, this time written in JavaScript. It serves to give the user more detailed information on specific businesses and uses the same style guide as the Overview app.

## Genie Agent
One of the main reasons we chose the Yelp data is because it afforded opportunities for the analysis of both structured and unstructured data. Embedding a Genie Agent in the apps we created allows us to give users more flexibility in their analysis and to better understand the unstructured text data of the reviews and tips in a way they couldn't with traditional analytics. The steps we took to create the Genie Agent were as follows:
1. Created an AI Search index on the Yelp reviews and tips. This allowed the Genie Agent to effectively search through unstructured text data to find information relevant to a user's question and avoided the need to depend on unreliable keyword searches
2. Created a metric view of the structured data pertaining to the businesses. This provided the Genie Agent with the context to properly query the tables without simply guessing at their structure and meaning
3. Added Markdown instructions to guide the Genie Agent's responses. These explained the purpose the agent served, when to use each source (the AI Search index or the metric view), and the style guide to which it should adhere so its visualizations would be consistent with those of the apps
