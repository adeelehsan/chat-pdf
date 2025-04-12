'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { AuthService } from './api';

type User = {
  username: string;
};

// Define an interface for API errors
interface ApiError {
  response?: {
    data?: {
      message?: string;
    };
  };
  message?: string;
}

type AuthContextType = {
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  register: (username: string, password: string) => Promise<{ success: boolean; message: string }>;
  isLoading: boolean;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    // Check for user and token on initial load
    const storedUser = localStorage.getItem('user');
    const token = AuthService.getToken();
    
    if (storedUser && token) {
      setUser(JSON.parse(storedUser));
    }
    setIsLoading(false);
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const response = await AuthService.login(username, password);
      
      if (response.data.success) {
        // Store user data
        const user = { username };
        localStorage.setItem('user', JSON.stringify(user));
        setUser(user);
        return true;
      }
      return false;
    } catch (error) {
      console.error('Login error:', error);
      return false;
    }
  };

  const register = async (username: string, password: string): Promise<{ success: boolean; message: string }> => {
    try {
      const response = await AuthService.register(username, password);
      
      if (response.data.success) {
        // Store user data
        const user = { username };
        localStorage.setItem('user', JSON.stringify(user));
        setUser(user);
        return { success: true, message: response.data.message };
      }
      return { success: false, message: response.data.message };
    } catch (error: unknown) {
      console.error('Registration error:', error);
      const apiError = error as ApiError;
      return { 
        success: false, 
        message: apiError.response?.data?.message || 'Registration failed' 
      };
    }
  };

  const logout = () => {
    AuthService.logout();
    localStorage.removeItem('user');
    setUser(null);
    router.push('/auth/login/');
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, register, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
} 