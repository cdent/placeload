placeload
---------

A script to create a set of resource providers with simple inventory
and membership in some aggregates in `placement service`_, so that
subsequent requests can be made (with ``curl`` or whatever works)
to test the service.

Uses asyncio to create them quickly.

Call it like::

    placeload <placement service url> [count]


* **count** is the number of resource providers to create

.. _placement service: https://developer.openstack.org/api-ref/placement/
