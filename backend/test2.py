import requests
res = requests.post('http://127.0.0.1:5000/api/import/validate', 
  files={'file': ('test.csv', 'id,name\n1,test')}, 
  data={'column_type_overrides': '{"id": "INTEGER"}'})
print("STATUS:", res.status_code)
print(res.text)
