import signal, os, socket, sys, struct, influxdb_client

from datetime import datetime as dt
from datetime import timedelta as td
from salsa20 import Salsa20_xor
from influxdb_client.client.write_api import SYNCHRONOUS

def salsa20_dec(dat):
	KEY = b'Simulator Interface Packet GT7 ver 0.0'
	# Seed IV is always located here
	oiv = dat[0x40:0x44]
	iv1 = int.from_bytes(oiv, byteorder='little')
	# Notice DEADBEAF, not DEADBEEF
	iv2 = iv1 ^ 0xDEADBEAF
	IV = bytearray()
	IV.extend(iv2.to_bytes(4, 'little'))
	IV.extend(iv1.to_bytes(4, 'little'))
	ddata = Salsa20_xor(dat, bytes(IV), KEY[0:32])
	magic = int.from_bytes(ddata[0:4], byteorder='little')
	if magic != 0x47375330:
		return bytearray(b'')
	return ddata

def send_hb(s):
	send_data = 'A'
	s.sendto(send_data.encode('utf-8'), (os.environ.get('PS5_IP'), int(os.environ.get('SENDPORT', 33739))))

def secondsToLaptime(seconds):
	remaining = seconds
	minutes = seconds // 60
	remaining = seconds % 60
	return '{:01.0f}:{:06.3f}'.format(minutes, remaining)

def main():
	influxdb_bucket = os.environ.get('INFLUXDB_V2_BUCKET')
	influxdb_org = os.environ.get('INFLUXDB_V2_ORG')

	client = influxdb_client.InfluxDBClient(
		url=os.environ.get('INFLUXDB_V2_URL'),
		token=os.environ.get('INFLUXDB_V2_TOKEN'),
	)

	write_api = client.write_api(write_options=SYNCHRONOUS)

	# ansi prefix
	pref = "\033["

	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.bind((os.environ.get('HOST_IP', '0.0.0.0'), int(os.environ.get('RECEIVEPORT', 33740))))
	s.settimeout(10)
	send_hb(s)

	previous_lap = -1
	pktid = 0
	pknt = 0
	heartbeat = 0
	
	while True:
		try:
			data, address = s.recvfrom(4096)
			pknt = pknt + 1
			ddata = salsa20_dec(data)
			if len(ddata) > 0 and struct.unpack('i', ddata[0x70:0x70+4])[0] > pktid:
				pktid = struct.unpack('i', ddata[0x70:0x70+4])[0]
				
				
				best_lap = struct.unpack('i', ddata[0x78:0x78+4])[0] / 1000
				last_lap = struct.unpack('i', ddata[0x7C:0x7C+4])[0] / 1000
				current_lap_raw = struct.unpack('h', ddata[0x74:0x74+2])[0]
				current_lap = 0

				if current_lap_raw > 0:
					dt_now = dt.now()
					if current_lap_raw != previous_lap:
						previous_lap = current_lap_raw
						dt_start = dt_now
					current_lap_time = dt_now - dt_start
					current_lap = current_lap_time.total_seconds()
				else:
					current_lap_time = 0
						
				track_time = str(td(seconds=round(struct.unpack('i', ddata[0x80:0x80+4])[0] / 1000)))

				total_laps = struct.unpack('h', ddata[0x76:0x76+2])[0]
				current_position = struct.unpack('h', ddata[0x84:0x84+2])[0]
				total_positions = struct.unpack('h', ddata[0x86:0x86+2])[0]

				cgear = struct.unpack('B', ddata[0x90:0x90+1])[0] & 0b00001111
				sgear = struct.unpack('B', ddata[0x90:0x90+1])[0] >> 4


				fuel_capacity = struct.unpack('f', ddata[0x48:0x48+4])[0]
				fuel_remaining = struct.unpack('f', ddata[0x44:0x44+4])[0]

				is_ev = False if fuel_capacity > 0 else True
				if is_ev:
					fuel_remaining = struct.unpack('f', ddata[0x44:0x44+4])[0]
					fuel_capacity = struct.unpack('f', ddata[0x48:0x48+4])[0]

				boost = struct.unpack('f', ddata[0x50:0x50+4])[0] - 1
				has_turbo = True if boost > -1 else False
				
				tire_diam_FL = struct.unpack('f', ddata[0xB4:0xB4+4])[0]
				tire_diam_FR = struct.unpack('f', ddata[0xB8:0xB8+4])[0]
				tire_diam_RL = struct.unpack('f', ddata[0xBC:0xBC+4])[0]
				tire_diam_RR = struct.unpack('f', ddata[0xC0:0xC0+4])[0]

				tire_speed_FL = abs(3.6 * tire_diam_FL * struct.unpack('f', ddata[0xA4:0xA4+4])[0])
				tire_speed_FR = abs(3.6 * tire_diam_FR * struct.unpack('f', ddata[0xA8:0xA8+4])[0])
				tire_speed_RL = abs(3.6 * tire_diam_RL * struct.unpack('f', ddata[0xAC:0xAC+4])[0])
				tire_speed_RR = abs(3.6 * tire_diam_RR * struct.unpack('f', ddata[0xB0:0xB0+4])[0])

				car_speed = 3.6 * struct.unpack('f', ddata[0x4C:0x4C+4])[0]
				
				tire_slip_ratio_FL = 0
				tire_slip_ratio_FR = 0
				tire_slip_ratio_RL = 0
				tire_slip_ratio_RR = 0

				if car_speed > 0:
					tire_slip_ratio_FL = (tire_speed_FL / car_speed)
					tire_slip_ratio_FR = (tire_speed_FR / car_speed)
					tire_slip_ratio_RL = (tire_speed_RL / car_speed)
					tire_slip_ratio_RR = (tire_speed_RR / car_speed)

				
				car_id = struct.unpack('i', ddata[0x124:0x124+4])[0]

				rpm = struct.unpack('f', ddata[0x3C:0x3C+4])[0]
				rpm_rev_warning = struct.unpack('H', ddata[0x88:0x88+2])[0]
				rpm_rev_limiter = struct.unpack('H', ddata[0x8A:0x8A+2])[0]

				breaking_force = struct.unpack('B', ddata[0x92:0x92+1])[0] / 2.55
				throttle = struct.unpack('B', ddata[0x91:0x91+1])[0] / 2.55

				estimate_top_speed = struct.unpack('h', ddata[0x8C:0x8C+2])[0]

				clutch = struct.unpack('f', ddata[0xF4:0xF4+4])[0]
				clutch_engaged = struct.unpack('f', ddata[0xF8:0xF8+4])[0]
				rpm_after_clutch = struct.unpack('f', ddata[0xFC:0xFC+4])[0]

				oil_temp = struct.unpack('f', ddata[0x5C:0x5C+4])[0]
				water_temp = struct.unpack('f', ddata[0x58:0x58+4])[0]
				oil_pressure = struct.unpack('f', ddata[0x54:0x54+4])[0]

				ride_height = 1000 * struct.unpack('f', ddata[0x38:0x38+4])[0]

				tire_temp_FL = struct.unpack('f', ddata[0x60:0x60+4])[0]
				tire_temp_FR = struct.unpack('f', ddata[0x64:0x64+4])[0]
				tire_temp_RL = struct.unpack('f', ddata[0x68:0x68+4])[0]
				tire_temp_RR = struct.unpack('f', ddata[0x6C:0x6C+4])[0]

				tire_diameter_FL = 200 * tire_diam_FL
				tire_diameter_FR = 200 * tire_diam_FR
				tire_diameter_RL = 200 * tire_diam_RL
				tire_diameter_RR = 200 * tire_diam_RR

				suspension_FL = struct.unpack('f', ddata[0xC4:0xC4+4])[0]
				suspension_FR = struct.unpack('f', ddata[0xC8:0xC8+4])[0]
				suspension_RL = struct.unpack('f', ddata[0xCC:0xCC+4])[0]
				suspension_RR = struct.unpack('f', ddata[0xD0:0xD0+4])[0]

				gear_1 = struct.unpack('f', ddata[0x104:0x104+4])[0]
				gear_2 = struct.unpack('f', ddata[0x108:0x108+4])[0]
				gear_3 = struct.unpack('f', ddata[0x10C:0x10C+4])[0]
				gear_4 = struct.unpack('f', ddata[0x110:0x110+4])[0]
				gear_5 = struct.unpack('f', ddata[0x114:0x114+4])[0]
				gear_6 = struct.unpack('f', ddata[0x118:0x118+4])[0]
				gear_7 = struct.unpack('f', ddata[0x11C:0x11C+4])[0]
				gear_8 = struct.unpack('f', ddata[0x120:0x120+4])[0]
				above_gear_8 = struct.unpack('f', ddata[0x100:0x100+4])[0]


				pos_X = struct.unpack('f', ddata[0x04:0x04+4])[0]
				pos_Y = struct.unpack('f', ddata[0x08:0x08+4])[0]
				pos_Z = struct.unpack('f', ddata[0x0C:0x0C+4])[0]

				velocity_X = struct.unpack('f', ddata[0x10:0x10+4])[0]
				velocity_Y = struct.unpack('f', ddata[0x14:0x14+4])[0]
				velocity_Z = struct.unpack('f', ddata[0x18:0x18+4])[0]

				rot_pitch = struct.unpack('f', ddata[0x1C:0x1C+4])[0]
				rot_yaw = struct.unpack('f', ddata[0x20:0x20+4])[0]
				rot_roll = struct.unpack('f', ddata[0x24:0x24+4])[0]

				angular_velocity_X = struct.unpack('f', ddata[0x2C:0x2C+4])[0]
				angular_velocity_Y = struct.unpack('f', ddata[0x30:0x30+4])[0]
				angular_velocity_Z = struct.unpack('f', ddata[0x34:0x34+4])[0]

				rotation = struct.unpack('f', ddata[0x28:0x28+4])[0]
			
				if os.environ.get('DEBUG', False):
					print([
						pktid,
						car_id,
						track_time,

						total_laps,
						current_position,
						total_positions,
						best_lap,
						last_lap,
						current_lap_raw,
						current_lap,

						car_speed,
						estimate_top_speed,
						clutch,
						clutch_engaged,
						rpm_after_clutch,
						oil_temp,
						water_temp,
						oil_pressure,
						rpm,
						rpm_rev_warning,
						rpm_rev_limiter,

						throttle,

						breaking_force,

						cgear,
						sgear,

						gear_1,
						gear_2,
						gear_3,
						gear_4,
						gear_5,
						gear_6,
						gear_7,
						gear_8,
						above_gear_8,
						
						is_ev,
						fuel_capacity,
						fuel_remaining,

						boost,
						has_turbo,

						ride_height,

						suspension_FL,
						suspension_FR,
						suspension_RL,
						suspension_RR,

						tire_temp_FL,
						tire_temp_FR,
						tire_temp_RL,
						tire_temp_RR,

						tire_diameter_FL,
						tire_diameter_FR,
						tire_diameter_RL,
						tire_diameter_RR,

						tire_diam_FL,
						tire_diam_FR,
						tire_diam_RL,
						tire_diam_RR,

						tire_speed_FL,
						tire_speed_FR,
						tire_speed_RL,
						tire_speed_RR,

						tire_slip_ratio_FL,
						tire_slip_ratio_FR,
						tire_slip_ratio_RL,
						tire_slip_ratio_RR,

						pos_X,
						pos_Y,
						pos_Z,

						velocity_X,
						velocity_Y,
						velocity_Z,

						rot_pitch,
						rot_yaw,
						rot_roll,

						angular_velocity_X,
						angular_velocity_Y,
						angular_velocity_Z,

						rotation,
					])

				record = influxdb_client.Point("gt7") \
					.field("pktid", pktid) \
					.field("car_id", car_id) \
					.field("track_time", track_time) \
					.field("total_laps", total_laps) \
					.field("current_position", current_position) \
					.field("total_positions", total_positions) \
					.field("best_lap", best_lap) \
					.field("last_lap", last_lap) \
					.field("current_lap_raw", float(current_lap_raw)) \
					.field("current_lap", current_lap) \
					.field("car_speed", car_speed) \
					.field("estimate_top_speed", estimate_top_speed) \
					.field("clutch", clutch) \
					.field("clutch_engaged", clutch_engaged) \
					.field("rpm_after_clutch", rpm_after_clutch) \
					.field("oil_temp", oil_temp) \
					.field("water_temp", water_temp) \
					.field("oil_pressure", oil_pressure) \
					.field("rpm", rpm) \
					.field("rpm_rev_warning", rpm_rev_warning) \
					.field("rpm_rev_limiter", rpm_rev_limiter) \
					.field("throttle", throttle) \
					.field("breaking_force", breaking_force) \
					.field("cgear", cgear) \
					.field("sgear", sgear) \
					.field("gear_1", gear_1) \
					.field("gear_2", gear_2) \
					.field("gear_3", gear_3) \
					.field("gear_4", gear_4) \
					.field("gear_5", gear_5) \
					.field("gear_6", gear_6) \
					.field("gear_7", gear_7) \
					.field("gear_8", gear_8) \
					.field("above_gear_8", above_gear_8) \
					.field("is_ev", is_ev) \
					.field("fuel_capacity", fuel_capacity) \
					.field("fuel_remaining", fuel_remaining) \
					.field("boost", boost) \
					.field("has_turbo", has_turbo) \
					.field("ride_height", ride_height) \
					.field("suspension_FL", suspension_FL) \
					.field("suspension_FR", suspension_FR) \
					.field("suspension_RL", suspension_RL) \
					.field("suspension_RR", suspension_RR) \
					.field("tire_temp_FL", tire_temp_FL) \
					.field("tire_temp_FR", tire_temp_FR) \
					.field("tire_temp_RL", tire_temp_RL) \
					.field("tire_temp_RR", tire_temp_RR) \
					.field("tire_diameter_FL", tire_diameter_FL) \
					.field("tire_diameter_FR", tire_diameter_FR) \
					.field("tire_diameter_RL", tire_diameter_RL) \
					.field("tire_diameter_RR", tire_diameter_RR) \
					.field("tire_diam_FL", tire_diam_FL) \
					.field("tire_diam_FR", tire_diam_FR) \
					.field("tire_diam_RL", tire_diam_RL) \
					.field("tire_diam_RR", tire_diam_RR) \
					.field("tire_speed_FL", tire_speed_FL) \
					.field("tire_speed_FR", tire_speed_FR) \
					.field("tire_speed_RL", tire_speed_RL) \
					.field("tire_speed_RR", tire_speed_RR) \
					.field("tire_slip_ratio_FL", tire_slip_ratio_FL) \
					.field("tire_slip_ratio_FR", tire_slip_ratio_FR) \
					.field("tire_slip_ratio_RL", tire_slip_ratio_RL) \
					.field("tire_slip_ratio_RR", tire_slip_ratio_RR) \
					.field("pos_X", pos_X) \
					.field("pos_Y", pos_Y) \
					.field("pos_Z", pos_Z) \
					.field("velocity_X", velocity_X) \
					.field("velocity_Y", velocity_Y) \
					.field("velocity_Z", velocity_Z) \
					.field("rot_pitch", rot_pitch) \
					.field("rot_yaw", rot_yaw) \
					.field("rot_roll", rot_roll) \
					.field("angular_velocity_X", angular_velocity_X) \
					.field("angular_velocity_Y", angular_velocity_Y) \
					.field("angular_velocity_Z", angular_velocity_Z) \
					.field("rotation", rotation)
				
				write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=record)
				

			if pknt > 100:
				send_hb(s)
				pknt = 0
		except Exception as e:
			print('Exception: {}'.format(e))
			pknt = 0
			pass

		if heartbeat > 100:
			print("Server is running")
			heartbeat = 0
		else:
			heartbeat += 1

print("Starting listning server")
main()