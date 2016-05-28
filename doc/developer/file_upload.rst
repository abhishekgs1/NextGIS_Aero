.. sectionauthor:: Dmitry Baryshnikov <dmitry.baryshnikov@nextgis.ru>

.. _ngw_file_upload:

file_upload component
=====================

File upload
--------------

For file upload following request exists:

..  http:post:: /api/component/file_upload/upload

    File upload request
    
    :form file: file path
    :form name: file name

Next multipart POST request follow. Request includes following form parameters:
`name` = "file name"

**Example request**:

.. sourcecode:: http

   POST /api/component/file_upload/upload HTTP/1.1
   Host: ngw_url
   Accept: */*
   
   file=\tmp\test.file&name=testfile
   

If request succeeded the uploaded file details will be returned:

**Example response body**:
    
.. sourcecode:: json 

    {
      "upload_meta": [
        {
          "id": "0eddf759-86d3-4fe0-b0f1-869fe783d2ed", 
          "mime_type": "application/octet-stream", 
          "name": "ngw1_1.zip", 
          "size": 2299
        }
      ]
    }

Several files upload
--------------------------

For several files upload following request exists:

..  http:post:: /api/component/file_upload/upload

    Several files upload request

    :form name: must be "files[]"

In `name` field must be file name and path (multipart POST request). 

If request succeeded the following response will be returned:
    
**Example response body**:
    
.. sourcecode:: json 

    {
      "upload_meta": [
        {
          "id": "b5c02d94-e1d7-40cf-b9c7-79bc9cca429d", 
          "mime_type": "application/octet-stream", 
          "name": "grunt_area_2_multipolygon.cpg", 
          "size": 5
        }, 
        {
          "id": "d8457f14-39cb-4f9d-bb00-452a381fa62e", 
          "mime_type": "application/x-dbf", 
          "name": "grunt_area_2_multipolygon.dbf", 
          "size": 36607
        }, 
        {
          "id": "1b0754f8-079d-4675-9367-36531da247e1", 
          "mime_type": "application/octet-stream", 
          "name": "grunt_area_2_multipolygon.prj", 
          "size": 138
        }, 
        {
          "id": "a34b5ab3-f3a5-4a60-835d-318e601d34df", 
          "mime_type": "application/x-esri-shape", 
          "name": "grunt_area_2_multipolygon.shp", 
          "size": 65132
        }, 
        {
          "id": "fb439bfa-1a63-4384-957d-ae57bb5eb67b", 
          "mime_type": "application/x-esri-shape", 
          "name": "grunt_area_2_multipolygon.shx", 
          "size": 1324
        }
      ]
    }

Change file
---------------

..  http:put:: /api/component/file_upload/upload


