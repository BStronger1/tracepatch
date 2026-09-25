from solution import parse_record
for i in range(200):
    print(f'INFO warmup record {i:04d}: synthetic diagnostic noise, no failure')
case = '"Doe, Jane",Paris,"said ""hello"""'
try:
    print('TARGET input:', repr(case), 'result:', parse_record(case))
except ValueError as exc:
    print('TARGET failure:', repr(case), str(exc))
for i in range(200):
    print(f'INFO cleanup record {i:04d}: synthetic diagnostic noise, no failure')
