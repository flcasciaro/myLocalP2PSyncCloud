# myP2PSync
SW applications system able to share and synchronize files among several devices using P2P file-sharing techniques. 

The aim of the myP2PSync project is to develop a local system able to provide fast, reliable and secure files synchronization. It keeps updated and equal copies of any kinds of files between different devices belonging to the same synchronization group. The update operation is not real-time, but just when the user decides to synchronize his local version with all the other devices. The system is therefore oriented to all users who want to easily create backup copies of files or simply use the same files on different devices. Also in the company field the application can be useful, allowing to synchronize files used by employees for example. In addition, the system can also be used for simple file sharing between different users.
The end user benefits from the functionality offered by the system through a client application with a graphical interface, simple and easy to use. Groups are registered and managed by a server application, which is executed locally, i.e. it is not a global server used by all the myP2PSync users. So a user who wants to use myP2PSync must know the location of a server, in terms of IP address and port number.
Access to a particular group is a function of a key that must be possessed. An user can belong to different groups, covering different roles, at the same time. 
The role of an user in a subscribed group can be:

- Master: it’s usually the creator of the group and main maintainer. It has access to information like the list of peers of the group and it can modifies the role of other peers, also electing another peer as Master. It can add, remove and update files in the group.
- Reader&Writer: users that can manage files in the group like the master, but they don’t have privileges regarding the other peers.
- ReadOnly: users that cannot manage file in the group. They can only receive files that belongs to a group, without the possibilities of add, remove or update files.

The role of a device is determined by the access token used during the group joining operation. Indeed, during the creation phase the user can specify two different tokens, one used to access the group as RW user and the other one for RO users.

File-sharing is performed using a Peer-to-Peer protocol inspired by the BitTorrent protocol. This allows the users network to decentralize traffic, avoiding the bottleneck effect on one or more central servers. In addition, a P2P protocol is much more stable and efficient as the number of users sharing the same file increases respect to a standard Client-Server approach. All traffic, both between devices and between server and single device, is transmitted in an encrypted and secure way.
The system is cross-platform, so it can be used on Windows, macOS and Linux, but it is not available on mobile devices at the moment.

# License

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
