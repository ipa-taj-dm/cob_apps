#!/usr/bin/python
#################################################################
##\file
#
# \note
#   Copyright (c) 2010 \n
#   Fraunhofer Institute for Manufacturing Engineering
#   and Automation (IPA) \n\n
#
#################################################################
#
# \note
#   Project name: care-o-bot
# \note
#   ROS stack name: cob_apps
# \note
#   ROS package name: cob_generic_states
#
# \author
#   Author: Daniel Maeki
# \author
#   Supervised by: Florian Weisshardt, email:florian.weisshardt@ipa.fhg.de
#
# \date Date of creation: May 2011
#
# \brief
#   Implements generic states which can be used in multiple scenarios.
#
#################################################################
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     - Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer. \n
#     - Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution. \n
#     - Neither the name of the Fraunhofer Institute for Manufacturing
#       Engineering and Automation (IPA) nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission. \n
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License LGPL as 
# published by the Free Software Foundation, either version 3 of the 
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License LGPL for more details.
# 
# You should have received a copy of the GNU Lesser General Public 
# License LGPL along with this program. 
# If not, see <http://www.gnu.org/licenses/>.
#
#################################################################


#------------------------------------------------------------------------------------------#
#-----	INFO						-------------------------------------------------------#

# \todo TODO merge the states 'linear_movement' and 'back_away'

#------------------------------------------------------------------------------------------#
#-----	IMPORT MODULES				-------------------------------------------------------#

import roslib
roslib.load_manifest('cob_generic_states')
import rospy
import smach
import smach_ros

from simple_script_server import *
sss = simple_script_server()

from cob_generic_states.srv import *

import tf
from tf.transformations import *
from actionlib_msgs.msg import *


#------------------------------------------------------------------------------------------#
#-----	SMACH STATES				-------------------------------------------------------#

class initialize(smach.State):

	def __init__(self):

		smach.State.__init__(
			self,
			outcomes=['initialized', 'failed'])
		
		# This state initializes all required components for executing a task.
		# However, this is not needed when running in simulation.

	def execute(self, userdata):

		#########################
		# initialize components #
		#########################
		
		handle_head = sss.init("head")
		if handle_head.get_error_code() != 0:
			return 'failed'

		handle_torso = sss.init("torso")
		if handle_torso.get_error_code() != 0:
			return 'failed'
			
		handle_tray = sss.init("tray")
		if handle_tray.get_error_code() != 0:
			return 'failed'

		#handle_arm = sss.init("arm")
		#if handle_arm.get_error_code() != 0:
		#	return 'failed'

		handle_sdh = sss.init("sdh")
		#if handle_sdh.get_error_code() != 0:
		#	return 'failed'

		handle_base = sss.init("base")
		if handle_base.get_error_code() != 0:
			return 'failed'		
		
		######################
		# recover components #
		######################
		
		handle_head = sss.recover("head")
		if handle_head.get_error_code() != 0:
			return 'failed'		
		
		handle_torso = sss.recover("torso")
		if handle_torso.get_error_code() != 0:
			return 'failed'
		
		handle_tray = sss.recover("tray")
		if handle_tray.get_error_code() != 0:
			return 'failed'

		handle_arm = sss.recover("arm")
		#if handle_arm.get_error_code() != 0:
		#	return 'failed'

		#handle_sdh = sss.recover("sdh")
		#if handle_sdh.get_error_code() != 0:
		#	return 'failed'

		handle_base = sss.recover("base")
		if handle_base.get_error_code() != 0:
			return 'failed'

		return 'initialized'

#------------------------------------------------------------------------------------------#
# This state moves the robot to the given pose.
class approach_pose(smach.State):

	def __init__(self, pose = "", mode = "omni", move_second = "False"):

		smach.State.__init__(
			self,
			outcomes=['succeeded', 'failed'],
			input_keys=['pose'],
			output_keys=['pose'])

		self.pose = pose
		self.mode = mode
		self.move_second = move_second

	def execute(self, userdata):

		# determine target position
		if self.pose != "":
			pose = self.pose
		elif type(userdata.pose) is str:
			pose = userdata.pose
		elif type(userdata.pose) is list:
			pose = []
			pose.append(userdata.pose[0])
			pose.append(userdata.pose[1])
			pose.append(userdata.pose[2])
		else: # this should never happen
			rospy.logerr("Invalid userdata 'pose'")
			return 'failed'

		# try reaching pose
		print "Trying to reach pose ", userdata.pose
		handle_base = sss.move("base", pose, False, mode=self.mode)
		move_second = self.move_second

		timeout = 0
		while True:
			if (handle_base.get_state() == 3) and (not move_second):
				# do a second movement to place the robot more exactly
				handle_base = sss.move("base", pose, False, mode=self.mode)
				move_second = True
			elif (handle_base.get_state() == 3) and (move_second):
				return 'succeeded'			

			# check if service is available
			service_full_name = '/base_controller/is_moving'
			try:
				rospy.wait_for_service(service_full_name,rospy.get_param('server_timeout',3))
			except rospy.ROSException, e:
				error_message = "%s"%e
				rospy.logerr("<<%s>> service not available, error: %s",service_full_name, error_message)
				return 'failed'
		
			# check if service is callable
			try:
				is_moving = rospy.ServiceProxy(service_full_name,Trigger)
				resp = is_moving()
			except rospy.ServiceException, e:
				error_message = "%s"%e
				rospy.logerr("calling <<%s>> service not successfull, error: %s",service_full_name, error_message)
				return 'failed'
		
			# evaluate service response
			if not resp.success.data: # robot stands still
				if timeout > 30:
					#sss.say(["I can not reach my target position because my path or target is blocked"],False)
					sss.play("WiMi_Satz19",False)
					timeout = 0
				else:
					timeout = timeout + 1
					rospy.sleep(1)
			else:
				timeout = 0

#------------------------------------------------------------------------------------------#

# This state moves the robot to the given pose without retry.
class approach_pose_without_retry(smach.State):

	def __init__(self, pose = "", mode = "omni", move_second = "False"):

		smach.State.__init__(
			self,
			outcomes=['succeeded', 'failed'],
			input_keys=['pose'],
			output_keys=['pose'])

		self.pose = pose
		self.mode = mode
		self.move_second = move_second

	def execute(self, userdata):

		# determine target position
		if self.pose != "":
			pose = self.pose
		elif type(userdata.pose) is str:
			pose = userdata.pose
		elif type(userdata.pose) is list:
			pose = []
			pose.append(userdata.pose[0])
			pose.append(userdata.pose[1])
			pose.append(userdata.pose[2])
		else: # this should never happen
			rospy.logerr("Invalid userdata 'pose'")
			return 'failed'

		# try reaching pose
		handle_base = sss.move("base", pose, False)
		move_second = False

		timeout = 0
		while True:
			if (handle_base.get_state() == 3) and (not move_second):
				# do a second movement to place the robot more exactly
				handle_base = sss.move("base", pose, False)
				move_second = True
			elif (handle_base.get_state() == 3) and (move_second):
				return 'succeeded'		

			# check if service is available
			service_full_name = '/base_controller/is_moving'
			try:
				rospy.wait_for_service(service_full_name,rospy.get_param('server_timeout',3))
			except rospy.ROSException, e:
				error_message = "%s"%e
				rospy.logerr("<<%s>> service not available, error: %s",service_full_name, error_message)
				return 'failed'

			# check if service is callable
			try:
				is_moving = rospy.ServiceProxy(service_full_name,Trigger)
				resp = is_moving()
			except rospy.ServiceException, e:
				error_message = "%s"%e
				rospy.logerr("calling <<%s>> service not successfull, error: %s",service_full_name, error_message)
				return 'failed'
		
			# evaluate service response
			if not resp.success.data: # robot stands still
				if timeout > 30:
					#sss.say(["I can not reach my target position because my path or target is blocked, I will abort."],False)
					rospy.wait_for_service('base_controller/stop',10)
					try:
						stop = rospy.ServiceProxy('base_controller/stop',Trigger)
						resp = stop()
					except rospy.ServiceException, e:
						error_message = "%s"%e
						rospy.logerr("calling <<%s>> service not successfull, error: %s",service_full_name, error_message)
					return 'failed'
				else:
					timeout = timeout + 1
					rospy.sleep(1)
			else:
				timeout = 0

#------------------------------------------------------------------------------------------#
