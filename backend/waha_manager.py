"""
WAHA Multi-Server Manager
Handles load balancing and instance management across multiple WAHA servers
"""
import os
import logging
from typing import List, Optional, Dict, Any
from supabase import Client
from waha_service import WahaService

logger = logging.getLogger(__name__)


class WahaServerManager:
    """Manages multiple WAHA servers for load balancing"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    async def get_available_server(self) -> Optional[Dict[str, Any]]:
        """
        Get next available WAHA server using load balancing
        Returns server with lowest load that's healthy
        """
        try:
            result = self.client.rpc('get_next_available_waha_server').execute()
            
            if not result.data:
                logger.error("No available WAHA servers found")
                return None
            
            server_id = result.data
            
            # Get full server details
            server = self.client.table('waha_servers')\
                .select('*')\
                .eq('id', server_id)\
                .single()\
                .execute()
            
            return server.data if server.data else None
            
        except Exception as e:
            logger.error(f"Error getting available server: {e}")
            return None
    
    async def get_default_server(self) -> Optional[Dict[str, Any]]:
        """Get the default WAHA server (fallback)"""
        try:
            result = self.client.table('waha_servers')\
                .select('*')\
                .eq('status', 'active')\
                .order('priority', desc=False)\
                .limit(1)\
                .execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting default server: {e}")
            return None
    
    async def get_server_for_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Get the WAHA server assigned to a company"""
        try:
            # Check if company already has an instance assigned
            instance = self.client.table('waha_instances')\
                .select('*, waha_servers(*)')\
                .eq('company_id', company_id)\
                .single()\
                .execute()
            
            if instance.data and instance.data.get('waha_servers'):
                return instance.data['waha_servers']
            
            # No instance yet, return None (will be assigned on first use)
            return None
            
        except Exception as e:
            logger.warning(f"No instance found for company {company_id}: {e}")
            return None
    
    async def assign_server_to_company(self, company_id: str, session_name: str) -> Optional[Dict[str, Any]]:
        """
        Assign a WAHA server to a company
        Creates instance record and increments server count
        """
        try:
            # Get best available server
            server = await self.get_available_server()
            
            if not server:
                logger.error("No available servers to assign")
                return None
            
            # Check if instance already exists
            existing = self.client.table('waha_instances')\
                .select('*')\
                .eq('company_id', company_id)\
                .execute()
            
            if existing.data:
                # Update existing
                instance = self.client.table('waha_instances')\
                    .update({
                        'server_id': server['id'],
                        'session_name': session_name,
                        'status': 'pending',
                        'updated_at': 'NOW()'
                    })\
                    .eq('company_id', company_id)\
                    .execute()
            else:
                # Create new instance
                instance = self.client.table('waha_instances')\
                    .insert({
                        'company_id': company_id,
                        'session_name': session_name,
                        'server_id': server['id'],
                        'status': 'pending'
                    })\
                    .execute()
            
            logger.info(f"Assigned server {server['name']} to company {company_id}")
            return server
            
        except Exception as e:
            logger.error(f"Error assigning server to company: {e}")
            return None
    
    async def get_waha_service_for_company(self, company_id: str) -> Optional[WahaService]:
        """
        Get WahaService instance for a company
        Automatically assigns server if not assigned yet
        """
        try:
            session_name = f"company_{company_id}"
            
            # Check if company has assigned server
            server = await self.get_server_for_company(company_id)
            
            if not server:
                # Assign new server
                logger.info(f"Assigning new server to company {company_id}")
                server = await self.assign_server_to_company(company_id, session_name)
                
                if not server:
                    # Fallback to default server
                    logger.warning("Using default server as fallback")
                    server = await self.get_default_server()
            
            if not server:
                logger.error("No WAHA servers available")
                return None
            
            # Create WahaService with assigned server
            return WahaService(
                waha_url=server['url'],
                api_key=server['api_key'],
                session_name=session_name
            )
            
        except Exception as e:
            logger.error(f"Error getting WAHA service for company: {e}")
            return None
    
    async def update_instance_status(self, company_id: str, status: str, connection_status: Optional[str] = None):
        """Update instance status"""
        try:
            update_data = {
                'status': status,
                'updated_at': 'NOW()'
            }
            
            if connection_status:
                update_data['connection_status'] = connection_status
            
            if status == 'connected':
                update_data['connected_at'] = 'NOW()'
            elif status == 'disconnected':
                update_data['disconnected_at'] = 'NOW()'
            
            self.client.table('waha_instances')\
                .update(update_data)\
                .eq('company_id', company_id)\
                .execute()
            
        except Exception as e:
            logger.error(f"Error updating instance status: {e}")
    
    async def list_servers(self) -> List[Dict[str, Any]]:
        """List all WAHA servers with stats"""
        try:
            result = self.client.table('waha_servers')\
                .select('*')\
                .order('priority', desc=False)\
                .execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error listing servers: {e}")
            return []
    
    async def add_server(
        self, 
        name: str, 
        url: str, 
        api_key: str,
        max_instances: int = 50,
        priority: int = 100,
        region: Optional[str] = None
    ) -> Optional[str]:
        """Add a new WAHA server"""
        try:
            result = self.client.table('waha_servers')\
                .insert({
                    'name': name,
                    'url': url,
                    'api_key': api_key,
                    'max_instances': max_instances,
                    'priority': priority,
                    'region': region,
                    'status': 'active',
                    'health_status': 'unknown'
                })\
                .execute()
            
            if result.data:
                logger.info(f"Added new WAHA server: {name}")
                return result.data[0]['id']
            
            return None
        except Exception as e:
            logger.error(f"Error adding server: {e}")
            return None
    
    async def update_server_health(self, server_id: str, health_status: str):
        """Update server health status"""
        try:
            self.client.table('waha_servers')\
                .update({
                    'health_status': health_status,
                    'last_health_check': 'NOW()',
                    'updated_at': 'NOW()'
                })\
                .eq('id', server_id)\
                .execute()
        except Exception as e:
            logger.error(f"Error updating server health: {e}")
    
    async def set_server_status(self, server_id: str, status: str):
        """Set server status (active, maintenance, offline)"""
        try:
            self.client.table('waha_servers')\
                .update({
                    'status': status,
                    'updated_at': 'NOW()'
                })\
                .eq('id', server_id)\
                .execute()
            
            logger.info(f"Server {server_id} status set to {status}")
        except Exception as e:
            logger.error(f"Error setting server status: {e}")


# Helper function to get manager instance
def get_waha_manager(supabase_client: Client) -> WahaServerManager:
    """Get WahaServerManager instance"""
    return WahaServerManager(supabase_client)
