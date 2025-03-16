# utils/textract_utils.py
import boto3

textract = boto3.client('textract')

def process_textract(bucket_name, file_name):
    response = textract.analyze_document(
        Document={
            'S3Object': {
                'Bucket': bucket_name,
                'Name': file_name
            }
        },
        FeatureTypes=['TABLES', 'FORMS']
    )
    return response
