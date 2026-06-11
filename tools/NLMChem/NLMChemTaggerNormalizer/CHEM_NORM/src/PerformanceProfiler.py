import collections
import datetime
import inspect

module_start = datetime.datetime.now()

timer2index = dict()
start_time = list()
elapsed_time = list()
call_count = list()

def get_index(timer):
	if timer in timer2index:
		return timer2index[timer]
	index = len(timer2index)
	timer2index[timer] = index
	start_time.append(None)
	elapsed_time.append(0)
	call_count.append(0)
	return index
	
def start(timer):
	index = get_index(timer)
	if not start_time[index] is None:
		print("WARN: called PerformanceProfiler.start(" + str(timer) + ") without ending previous call")
	start_time[index] = datetime.datetime.now()

def end(timer):
	index = get_index(timer)
	if start_time[index] is None:
		print("WARN: called PerformanceProfiler.end(" + str(timer) + ") without starting call")
		return
	diff = datetime.datetime.now() - start_time[index]
	start_time[index] = None
	elapsed_time[index] += diff.total_seconds() * 1000
	call_count[index] += 1
		
def visualize():
	# TODO Format output nicely
	output = list()
	for timer, index in timer2index.items():
		calls = call_count[index]
		output.append((elapsed_time[index], calls, timer))
	output.sort(reverse = True)
	for item in output:
		elapsed = item[0]
		calls = item[1]
		timer = item[2]
		average = 0
		if calls > 0:
			average = elapsed / calls
		print("PERFORMANCE " + str(timer) + " completed " + str(calls) + " calls, elapsed time = " + str(elapsed) + "ms, average time = " + str(average) + "ms")

