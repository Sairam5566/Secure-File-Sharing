import requests
import sqlite3

BASE_URL = 'http://127.0.0.1:8000'

requests.post(f'{BASE_URL}/register', json={'username': 'admin_test2', 'email': 'adm2@test.com', 'password': 'password'})
requests.post(f'{BASE_URL}/register', json={'username': 'reg_test2', 'email': 'reg2@test.com', 'password': 'password'})

resp_admin = requests.post(f'{BASE_URL}/login', data={'username': 'admin_test2', 'password': 'password'})
admin_token = resp_admin.json()['access_token']

resp_reg = requests.post(f'{BASE_URL}/login', data={'username': 'reg_test2', 'password': 'password'})
reg_token = resp_reg.json()['access_token']

conn = sqlite3.connect('secure_file_sharing.db')
c = conn.cursor()
c.execute("UPDATE users SET role = 'admin' WHERE username = 'admin_test2'")
conn.commit()

c.execute("INSERT INTO access_logs (user_id, access_time, access_status, action_type, is_anomalous, anomaly_score) VALUES ((SELECT id FROM users WHERE username='reg_test2'), '2023-01-01', 'denied', 'download', 1, 0.15)")
c.execute("INSERT INTO access_logs (user_id, access_time, access_status, action_type, is_anomalous, anomaly_score) VALUES ((SELECT id FROM users WHERE username='reg_test2'), '2023-01-02', 'denied', 'upload', 1, 0.12)")
c.execute("INSERT INTO access_logs (user_id, access_time, access_status, action_type, is_anomalous, anomaly_score) VALUES ((SELECT id FROM users WHERE username='admin_test2'), '2023-01-03', 'denied', 'download', 1, 0.22)")
conn.commit()
conn.close()

r_admin = requests.get(f'{BASE_URL}/access-logs/?is_anomalous=true', headers={'Authorization': f'Bearer {admin_token}'})
admin_logs = r_admin.json()
print('Admin fetched:', len(admin_logs), 'logs')
for log in admin_logs:
    print('  - User ID:', log['user_id'], 'Score:', log['anomaly_score'])

r_reg = requests.get(f'{BASE_URL}/access-logs/?is_anomalous=true', headers={'Authorization': f'Bearer {reg_token}'})
reg_logs = r_reg.json()
print('Reg fetched:', len(reg_logs), 'logs')
for log in reg_logs:
    print('  - User ID:', log['user_id'], 'Score:', log['anomaly_score'])
