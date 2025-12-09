import { useQuery } from '@tanstack/react-query'
import { healthAPI } from '../services/api'
import { POLLING_INTERVALS } from '../utils/constants'

/**
 * Hook to fetch and monitor system health status
 */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await healthAPI.check()
      return response.data
    },
    refetchInterval: POLLING_INTERVALS.HEALTH_CHECK,
    refetchOnWindowFocus: true,
    staleTime: 20000, // Consider data stale after 20 seconds
    cacheTime: 30000, // Keep in cache for 30 seconds
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    onError: (error) => {
      console.error('Health check failed:', error)
    }
  })
}

/**
 * Hook to get derived health status information
 */
export function useHealthStatus() {
  const { data: health, isError, isLoading } = useHealth()

  const isHealthy = health?.status === 'healthy' && !isError
  const hasStorageInfo = health?.storage != null
  const workerStats = health?.worker_stats || {}

  return {
    isHealthy,
    isLoading,
    isError,
    hasStorageInfo,
    health,
    workerStats,
    // Derived status
    systemStatus: isError ? 'offline' : isHealthy ? 'online' : 'degraded'
  }
}