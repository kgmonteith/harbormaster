from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView
from django.utils import timezone
from django.db.models import Max
from harbormaster.models import *
import harbormaster.util as util
from django.db.models import Q
import logging, re, datetime, json
import ais
from ws4redis.redis_store import RedisMessage
from ws4redis.publisher import RedisPublisher

logger = logging.getLogger(__name__)
aidvm_match = re.compile("^\!AIVDM,\d,\d,\d*,.+\*[0-9A-Fa-f]{2}")

fragment_buffer = {}

def enrichContact(contact):
	if(contact.ship_type is not None):
		contact.readable_ship_type = util.readable_ship_type(contact.ship_type)
	if(contact.dim_to_bow is not None):
		contact.length = contact.dim_to_bow + contact.dim_to_stern
		contact.width = contact.dim_to_port + contact.dim_to_starboard
	if(contact.max_speed >= 102.3):
		contact.max_speed = ""
	contact.navigation_status_text = util.get_navigation_text(contact.latest_navigation_status)
	return contact

def map(request, active="active all"):
	contacts = Contact.objects.all()
	collection_labels = CollectionLabel.objects.order_by('-start_date')

	current_label = request.POST.get("currentLabel", "*")
	if(current_label != "*"):
		contacts = contacts.filter(report__collection_label__name=current_label).distinct()

	if("ships" in active):
		contacts = contacts.filter(mmsi_type="Ship")
	elif("other" in active):
		contacts = contacts.filter(~Q(mmsi_type = "Ship"))
	if("active" in active):
		contacts = contacts.filter(last_sighting__gt=timezone.now() - datetime.timedelta(minutes=30))
		
	for contact in contacts:
		contact = enrichContact(contact)

	context = {'contacts': contacts, 'collection_labels': collection_labels, 'current_label': current_label, 'active': active}
	return render(request, 'map/map.html', context)


def list(request, active="active ships"):
	contacts = Contact.objects.all()
	collection_labels = CollectionLabel.objects.order_by('-start_date')

	current_label = request.POST.get("currentLabel", "*")
	logging.error(current_label)
	if(current_label != "*"):
		contacts = contacts.filter(report__collection_label__name=current_label).distinct()

	if("ships" in active):
		contacts = contacts.filter(mmsi_type="Ship")
	elif("other" in active):
		contacts = contacts.filter(~Q(mmsi_type = "Ship"))
	template = 'list/ship_list_historic.html'
	if("active" in active):
		contacts = contacts.filter(last_sighting__gt=timezone.now() - datetime.timedelta(minutes=30))
		template = 'list/ship_list_active.html'
		
	for contact in contacts:
		contact = enrichContact(contact)
	context = {'contacts': contacts, 'collection_labels': collection_labels, 'current_label': current_label, 'active': active}
	return render(request, template, context)

def getContactJson(request, mmsi):
	contact = Contact.objects.get(mmsi=mmsi)
	contact = enrichContact(contact)
	data = {
		'mmsi': mmsi,
		'length': contact.length if contact.length is not None else 0,
		'width': contact.width if contact.width is not None else 0,
		'to_bow': contact.dim_to_bow,
		'to_port': contact.dim_to_port,
		'name': contact.name
	}
	return HttpResponse(json.dumps(data), content_type='application/json')

def reprocess(request):
	contacts = Contact.objects.all()
	for contact in contacts:
		contact.last_sighting = None
		contact.save()

	# Gets most recent report of each type per contact.
	# Seems like magic but works... django makes grouping hard.
	qs = Report.objects.all()
	latest_dates = qs.values('contact', 'report_type').annotate(latest_time_received=Max('time_received'))
	reports = qs.filter(time_received__in=latest_dates.values('latest_time_received')).order_by('-time_received')
	for report in reports:
		report.update_contact()
	return render(request, 'blank.html')

@csrf_exempt
def input(request, collection_label = None):
	if(len(request.body) == 0 or not aidvm_match.match(request.body)):
		return render(request, 'error.html')
	messages = request.body.splitlines(False)

	if(collection_label is not None):
		collection_label, created = CollectionLabel.objects.get_or_create(name=collection_label)

	for message in messages:
		split_message = message.split(',')
		sentence = split_message[5]
		fill_bits = int(split_message[-1].split('*')[0])


		if(int(split_message[1]) > 1): # fragmented message
			message_id = split_message[3]
			this_frag = int(split_message[2])
			total_frags = int(split_message[1])

			if(message_id not in fragment_buffer.keys()):
				fragment_buffer[message_id] = [0] * total_frags
			fragment_buffer[message_id][this_frag-1] = split_message
			if(this_frag == total_frags): # last fragment of a fragmented message
				if(len(fragment_buffer[message_id]) != total_frags): # missed a message
					# purge fragments and error out
					del fragment_buffer[message_id]
					return render(request, 'error.html')
				sentence = ''
				for i in range(0, total_frags):
					sentence += fragment_buffer[message_id][i][5]
				del fragment_buffer[message_id]
			else:
				return render(request, 'blank.html')
		
		# it should now be safe to assume the sentence is complete
		report_type = ord(sentence[0])-48
		if report_type > 48:
			report_type = report_type - 8
		# catch potential Type 24 bug
		if(report_type == 24 and len(sentence) == 27):
			sentence += '0'
		try:
			decoded = ais.decode(sentence, fill_bits)
			decoded['mmsi'] = format(decoded['mmsi'], '09')
			#if(report_type == 5 or report_type == 24):
			#	logger.error(decoded)
			contact, created = Contact.objects.get_or_create(mmsi=decoded['mmsi'])
			if(collection_label not in contact.collection_labels.all()):
				contact.collection_labels.add(collection_label)
				contact.save()
			report = Report.objects.create(sentence=sentence, fill_bits=fill_bits, contact=contact, report_type=report_type, collection_label=collection_label, decoded=decoded)
			
			# Publish to stream
			if(report_type in util.position_types):
				heading = report.decoded['true_heading']
				if(heading == 511 and report.decoded['cog'] > 0):
					heading = report.decoded['cog']
				message = RedisMessage(json.dumps({'type': 'position', 'collection_label': collection_label.name, 'mmsi': report.contact.mmsi, 'lat': report.decoded['y'], 'lng': report.decoded['x'], 'speed': report.decoded['sog'], 'heading': heading}))
				RedisPublisher(facility='jsonStream', broadcast=True).publish_message(message)
		except ais.DecodeError:
			# message could not be parsed. add a RawReport instead of Report
			logger.error("Decode error! Message: %s" % message)
			raw_report = RawReport(sentence=sentence, fill_bits=fill_bits, decode_error=True)
			raw_report.save()
	return render(request, 'blank.html')