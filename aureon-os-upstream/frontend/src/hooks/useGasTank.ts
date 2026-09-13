import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useToast } from '@/hooks/use-toast';

interface GasTankState {
  balance: number;
  initialBalance: number;
  highWaterMark: number;
  feeRate: number;
  membershipType: 'founder' | 'standard';
  feesPaidToday: number;
  totalFeesPaid: number;
  status: 'ACTIVE' | 'LOW' | 'CRITICAL' | 'EMPTY' | 'PAUSED';
  canTrade: boolean;
  isLoading: boolean;
}

export const GAS_TANK_TOPUP_STATUS = 'PROVIDER_VERIFIED_TOPUP_REQUIRED' as const;

export const useGasTank = (userId: string | null) => {
  const { toast } = useToast();
  const [receipt, setReceipt] = useState<{ observed: boolean; userId: string | null; receivedAt: number | null; reason: string }>({
    observed: false, userId: null, receivedAt: null, reason: 'Account receipt unavailable',
  });
  const [state, setState] = useState<GasTankState>({
    balance: 0,
    initialBalance: 0,
    highWaterMark: 0,
    feeRate: 0.20,
    membershipType: 'standard',
    feesPaidToday: 0,
    totalFeesPaid: 0,
    status: 'EMPTY',
    canTrade: false,
    isLoading: true,
  });

  // Fetch initial gas tank data
  useEffect(() => {
    let cancelled = false;
    setReceipt({ observed: false, userId, receivedAt: null, reason: userId ? 'Reading account' : 'Sign in to view account' });
    if (!userId) {
      setState(prev => ({ ...prev, isLoading: false }));
      return;
    }

    const fetchGasTank = async () => {
      const { data, error } = await supabase
        .from('gas_tank_accounts')
        .select('*')
        .eq('user_id', userId)
        .single();

      if (cancelled) return;

      if (error && error.code !== 'PGRST116') {
        console.error('Error fetching gas tank:', error);
        setReceipt({ observed: false, userId, receivedAt: null, reason: 'Account query failed' });
        setState(prev => ({ ...prev, isLoading: false }));
        return;
      }

      if (data) {
        setReceipt({ observed: true, userId, receivedAt: Date.now(), reason: 'Successful account row read' });
        setState({
          balance: parseFloat(data.balance as any),
          initialBalance: parseFloat(data.initial_balance as any),
          highWaterMark: parseFloat(data.high_water_mark as any),
          feeRate: parseFloat(data.fee_rate as any),
          membershipType: data.membership_type as 'founder' | 'standard',
          feesPaidToday: parseFloat(data.fees_paid_today as any),
          totalFeesPaid: parseFloat(data.total_fees_paid as any),
          status: data.status as any,
          canTrade: data.balance > 0 && data.status !== 'PAUSED' && data.status !== 'EMPTY',
          isLoading: false,
        });
      } else {
        setReceipt({ observed: false, userId, receivedAt: null, reason: 'Account row unavailable' });
        setState(prev => ({ ...prev, isLoading: false }));
      }
    };

    fetchGasTank();
    return () => { cancelled = true; };
  }, [userId]);

  // Subscribe to real-time updates
  useEffect(() => {
    if (!userId) return;

    const channel = supabase
      .channel('gas-tank-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'gas_tank_accounts',
          filter: `user_id=eq.${userId}`,
        },
        (payload) => {
          console.log('Gas tank updated:', payload);
          const data = payload.new as any;

          if (payload.eventType === 'DELETE') {
            setReceipt({ observed: false, userId, receivedAt: null, reason: 'Account row removed' });
            return;
          }
          
          if (data) {
            setReceipt({ observed: true, userId, receivedAt: Date.now(), reason: 'Account row update received' });
            const newState = {
              balance: parseFloat(data.balance),
              initialBalance: parseFloat(data.initial_balance),
              highWaterMark: parseFloat(data.high_water_mark),
              feeRate: parseFloat(data.fee_rate),
              membershipType: data.membership_type as 'founder' | 'standard',
              feesPaidToday: parseFloat(data.fees_paid_today),
              totalFeesPaid: parseFloat(data.total_fees_paid),
              status: data.status as any,
              canTrade: data.balance > 0 && data.status !== 'PAUSED' && data.status !== 'EMPTY',
              isLoading: false,
            };

            setState(newState);

            // Show status change toasts
            if (data.status === 'LOW' && state.status !== 'LOW') {
              toast({
                title: '🟡 Gas Tank Low',
                description: `Balance: £${parseFloat(data.balance).toFixed(2)}. Consider topping up.`,
                variant: 'default',
              });
            } else if (data.status === 'CRITICAL' && state.status !== 'CRITICAL') {
              toast({
                title: '🔴 Gas Tank Critical',
                description: `Balance: £${parseFloat(data.balance).toFixed(2)}. Top up soon!`,
                variant: 'destructive',
              });
            } else if (data.status === 'EMPTY' && state.status !== 'EMPTY') {
              toast({
                title: '⚫ Gas Tank Empty',
                description: 'Trading paused. Please top up to resume.',
                variant: 'destructive',
              });
            }
          }
        }
      )
      .subscribe();

    // Subscribe to transactions for fee deduction notifications
    const transactionsChannel = supabase
      .channel('gas-tank-transactions')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'gas_tank_transactions',
        },
        async (payload) => {
          const transaction = payload.new as any;
          
          // Check if this transaction belongs to current user
          const { data: account } = await supabase
            .from('gas_tank_accounts')
            .select('user_id')
            .eq('id', transaction.account_id)
            .single();

          if (account && account.user_id === userId && transaction.type === 'FEE_DEDUCTION') {
            // Play sound effect
            const audio = new Audio('/notification.mp3');
            audio.volume = 0.3;
            audio.play().catch(console.error);

            toast({
              title: '⛽ Fee Deducted',
              description: `£${Math.abs(parseFloat(transaction.amount)).toFixed(2)} performance fee deducted`,
              variant: 'default',
            });
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
      supabase.removeChannel(transactionsChannel);
    };
  }, [userId, state.status, toast]);

  return {
    ...state,
    receipt: { ...receipt, observed: receipt.observed && receipt.userId === userId },
    topUp: {
      available: false,
      reason: GAS_TANK_TOPUP_STATUS,
    },
  };
};
