// Bu dosya scripts/gen-types.mjs ile veritabanı şemasından üretilmiştir. Elle düzenlemeyin.
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]

export type Database = {
  public: {
    Tables: {
      activity_logs: {
        Row: {
          action: string
          actor_email: string | null
          actor_id: string | null
          created_at: string
          details: Json
          entity_id: string | null
          entity_label: string | null
          entity_type: string
          id: number
        }
        Insert: {
          action: string
          actor_email?: string | null
          actor_id?: string | null
          created_at?: string
          details?: Json
          entity_id?: string | null
          entity_label?: string | null
          entity_type: string
          id?: number
        }
        Update: {
          action?: string
          actor_email?: string | null
          actor_id?: string | null
          created_at?: string
          details?: Json
          entity_id?: string | null
          entity_label?: string | null
          entity_type?: string
          id?: number
        }
        Relationships: [
          {
            foreignKeyName: "activity_logs_actor_id_fkey"
            columns: ["actor_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      materials: {
        Row: {
          category: string
          created_at: string
          currency: string
          description: string | null
          id: string
          is_programmer_extra: boolean
          name: string
          notes: string | null
          product_url: string | null
          purchase_status: Database["public"]["Enums"]["purchase_status"]
          purchased_quantity: number
          ref_currency: string
          ref_quantity: number | null
          ref_stated_total_max: number | null
          ref_stated_total_min: number | null
          ref_unit_price_max: number | null
          ref_unit_price_min: number | null
          required_quantity: number
          slug: string
          sort_order: number
          source_name: string | null
          supplier: string | null
          unit_price: number | null
          updated_at: string
          updated_by: string | null
        }
        Insert: {
          category: string
          created_at?: string
          currency?: string
          description?: string | null
          id?: string
          is_programmer_extra?: boolean
          name: string
          notes?: string | null
          product_url?: string | null
          purchase_status?: Database["public"]["Enums"]["purchase_status"]
          purchased_quantity?: number
          ref_currency?: string
          ref_quantity?: number | null
          ref_stated_total_max?: number | null
          ref_stated_total_min?: number | null
          ref_unit_price_max?: number | null
          ref_unit_price_min?: number | null
          required_quantity?: number
          slug: string
          sort_order?: number
          source_name?: string | null
          supplier?: string | null
          unit_price?: number | null
          updated_at?: string
          updated_by?: string | null
        }
        Update: {
          category?: string
          created_at?: string
          currency?: string
          description?: string | null
          id?: string
          is_programmer_extra?: boolean
          name?: string
          notes?: string | null
          product_url?: string | null
          purchase_status?: Database["public"]["Enums"]["purchase_status"]
          purchased_quantity?: number
          ref_currency?: string
          ref_quantity?: number | null
          ref_stated_total_max?: number | null
          ref_stated_total_min?: number | null
          ref_unit_price_max?: number | null
          ref_unit_price_min?: number | null
          required_quantity?: number
          slug?: string
          sort_order?: number
          source_name?: string | null
          supplier?: string | null
          unit_price?: number | null
          updated_at?: string
          updated_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "materials_updated_by_fkey"
            columns: ["updated_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      media_files: {
        Row: {
          bucket_name: string
          category: Database["public"]["Enums"]["media_category"]
          component_id: string | null
          created_at: string
          description: string | null
          file_name: string
          file_size: number
          id: string
          is_public: boolean | null
          mime_type: string
          original_file_name: string
          progress_update_id: string | null
          simulation_id: string | null
          storage_path: string
          title: string
          updated_at: string
          uploaded_by: string | null
        }
        Insert: {
          bucket_name: string
          category: Database["public"]["Enums"]["media_category"]
          component_id?: string | null
          created_at?: string
          description?: string | null
          file_name: string
          file_size: number
          id?: string
          is_public?: never
          mime_type: string
          original_file_name: string
          progress_update_id?: string | null
          simulation_id?: string | null
          storage_path: string
          title: string
          updated_at?: string
          uploaded_by?: string | null
        }
        Update: {
          bucket_name?: string
          category?: Database["public"]["Enums"]["media_category"]
          component_id?: string | null
          created_at?: string
          description?: string | null
          file_name?: string
          file_size?: number
          id?: string
          is_public?: never
          mime_type?: string
          original_file_name?: string
          progress_update_id?: string | null
          simulation_id?: string | null
          storage_path?: string
          title?: string
          updated_at?: string
          uploaded_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "media_files_component_id_fkey"
            columns: ["component_id"]
            isOneToOne: false
            referencedRelation: "project_components"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "media_files_progress_update_id_fkey"
            columns: ["progress_update_id"]
            isOneToOne: false
            referencedRelation: "progress_updates"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "media_files_simulation_id_fkey"
            columns: ["simulation_id"]
            isOneToOne: false
            referencedRelation: "simulations"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "media_files_uploaded_by_fkey"
            columns: ["uploaded_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          created_at: string
          email: string | null
          full_name: string | null
          id: string
          role: Database["public"]["Enums"]["app_role"]
          updated_at: string
        }
        Insert: {
          created_at?: string
          email?: string | null
          full_name?: string | null
          id: string
          role?: Database["public"]["Enums"]["app_role"]
          updated_at?: string
        }
        Update: {
          created_at?: string
          email?: string | null
          full_name?: string | null
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          updated_at?: string
        }
        Relationships: []
      }
      progress_updates: {
        Row: {
          component_id: string | null
          created_at: string
          created_by: string | null
          description: string | null
          id: string
          is_published: boolean
          phase_id: string | null
          progress_value: number | null
          status: Database["public"]["Enums"]["work_status"]
          title: string
          update_date: string
          updated_at: string
        }
        Insert: {
          component_id?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          id?: string
          is_published?: boolean
          phase_id?: string | null
          progress_value?: number | null
          status?: Database["public"]["Enums"]["work_status"]
          title: string
          update_date?: string
          updated_at?: string
        }
        Update: {
          component_id?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          id?: string
          is_published?: boolean
          phase_id?: string | null
          progress_value?: number | null
          status?: Database["public"]["Enums"]["work_status"]
          title?: string
          update_date?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "progress_updates_component_id_fkey"
            columns: ["component_id"]
            isOneToOne: false
            referencedRelation: "project_components"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "progress_updates_created_by_fkey"
            columns: ["created_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "progress_updates_phase_id_fkey"
            columns: ["phase_id"]
            isOneToOne: false
            referencedRelation: "project_phases"
            referencedColumns: ["id"]
          },
        ]
      }
      project_components: {
        Row: {
          architecture_notes: string | null
          created_at: string
          description: string | null
          id: string
          name: string
          name_en: string | null
          slug: string
          sort_order: number
          status: Database["public"]["Enums"]["work_status"]
          updated_at: string
        }
        Insert: {
          architecture_notes?: string | null
          created_at?: string
          description?: string | null
          id?: string
          name: string
          name_en?: string | null
          slug: string
          sort_order?: number
          status?: Database["public"]["Enums"]["work_status"]
          updated_at?: string
        }
        Update: {
          architecture_notes?: string | null
          created_at?: string
          description?: string | null
          id?: string
          name?: string
          name_en?: string | null
          slug?: string
          sort_order?: number
          status?: Database["public"]["Enums"]["work_status"]
          updated_at?: string
        }
        Relationships: []
      }
      project_phases: {
        Row: {
          created_at: string
          deliverable: string | null
          description: string | null
          id: string
          route: string | null
          semester: Database["public"]["Enums"]["semester"]
          short_title: string | null
          slug: string
          sort_order: number
          start_date: string | null
          status: Database["public"]["Enums"]["phase_status"]
          target_date: string | null
          title: string
          updated_at: string
          weight: number
        }
        Insert: {
          created_at?: string
          deliverable?: string | null
          description?: string | null
          id?: string
          route?: string | null
          semester: Database["public"]["Enums"]["semester"]
          short_title?: string | null
          slug: string
          sort_order?: number
          start_date?: string | null
          status?: Database["public"]["Enums"]["phase_status"]
          target_date?: string | null
          title: string
          updated_at?: string
          weight?: number
        }
        Update: {
          created_at?: string
          deliverable?: string | null
          description?: string | null
          id?: string
          route?: string | null
          semester?: Database["public"]["Enums"]["semester"]
          short_title?: string | null
          slug?: string
          sort_order?: number
          start_date?: string | null
          status?: Database["public"]["Enums"]["phase_status"]
          target_date?: string | null
          title?: string
          updated_at?: string
          weight?: number
        }
        Relationships: []
      }
      project_settings: {
        Row: {
          academic_year: string | null
          course: string | null
          current_phase_id: string | null
          default_currency: string
          github_url: string | null
          id: boolean
          project_description: string | null
          project_status: string | null
          project_subtitle: string | null
          project_title: string
          supervisor: string | null
          tasarim_ii_active: boolean
          team_members: Json
          university: string | null
          updated_at: string
          updated_by: string | null
          usd_try_rate: number | null
          usd_try_rate_date: string | null
        }
        Insert: {
          academic_year?: string | null
          course?: string | null
          current_phase_id?: string | null
          default_currency?: string
          github_url?: string | null
          id?: boolean
          project_description?: string | null
          project_status?: string | null
          project_subtitle?: string | null
          project_title?: string
          supervisor?: string | null
          tasarim_ii_active?: boolean
          team_members?: Json
          university?: string | null
          updated_at?: string
          updated_by?: string | null
          usd_try_rate?: number | null
          usd_try_rate_date?: string | null
        }
        Update: {
          academic_year?: string | null
          course?: string | null
          current_phase_id?: string | null
          default_currency?: string
          github_url?: string | null
          id?: boolean
          project_description?: string | null
          project_status?: string | null
          project_subtitle?: string | null
          project_title?: string
          supervisor?: string | null
          tasarim_ii_active?: boolean
          team_members?: Json
          university?: string | null
          updated_at?: string
          updated_by?: string | null
          usd_try_rate?: number | null
          usd_try_rate_date?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "project_settings_current_phase_id_fkey"
            columns: ["current_phase_id"]
            isOneToOne: false
            referencedRelation: "project_phases"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "project_settings_updated_by_fkey"
            columns: ["updated_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      project_tasks: {
        Row: {
          assigned_to: string | null
          completed_at: string | null
          component_id: string | null
          created_at: string
          created_by: string | null
          description: string | null
          due_date: string | null
          id: string
          phase_id: string
          priority: Database["public"]["Enums"]["task_priority"]
          sort_order: number
          status: Database["public"]["Enums"]["work_status"]
          title: string
          updated_at: string
          weight: number
        }
        Insert: {
          assigned_to?: string | null
          completed_at?: string | null
          component_id?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          due_date?: string | null
          id?: string
          phase_id: string
          priority?: Database["public"]["Enums"]["task_priority"]
          sort_order?: number
          status?: Database["public"]["Enums"]["work_status"]
          title: string
          updated_at?: string
          weight?: number
        }
        Update: {
          assigned_to?: string | null
          completed_at?: string | null
          component_id?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          due_date?: string | null
          id?: string
          phase_id?: string
          priority?: Database["public"]["Enums"]["task_priority"]
          sort_order?: number
          status?: Database["public"]["Enums"]["work_status"]
          title?: string
          updated_at?: string
          weight?: number
        }
        Relationships: [
          {
            foreignKeyName: "project_tasks_assigned_to_fkey"
            columns: ["assigned_to"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "project_tasks_component_id_fkey"
            columns: ["component_id"]
            isOneToOne: false
            referencedRelation: "project_components"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "project_tasks_created_by_fkey"
            columns: ["created_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "project_tasks_phase_id_fkey"
            columns: ["phase_id"]
            isOneToOne: false
            referencedRelation: "project_phases"
            referencedColumns: ["id"]
          },
        ]
      }
      purchases: {
        Row: {
          created_at: string
          currency: string
          id: string
          material_id: string
          notes: string | null
          purchase_date: string
          purchased_by: string | null
          quantity: number
          receipt_file_id: string | null
          supplier: string | null
          unit_price: number | null
          updated_at: string
        }
        Insert: {
          created_at?: string
          currency?: string
          id?: string
          material_id: string
          notes?: string | null
          purchase_date: string
          purchased_by?: string | null
          quantity: number
          receipt_file_id?: string | null
          supplier?: string | null
          unit_price?: number | null
          updated_at?: string
        }
        Update: {
          created_at?: string
          currency?: string
          id?: string
          material_id?: string
          notes?: string | null
          purchase_date?: string
          purchased_by?: string | null
          quantity?: number
          receipt_file_id?: string | null
          supplier?: string | null
          unit_price?: number | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "purchases_material_id_fkey"
            columns: ["material_id"]
            isOneToOne: false
            referencedRelation: "materials"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "purchases_purchased_by_fkey"
            columns: ["purchased_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "purchases_receipt_file_id_fkey"
            columns: ["receipt_file_id"]
            isOneToOne: false
            referencedRelation: "media_files"
            referencedColumns: ["id"]
          },
        ]
      }
      simulations: {
        Row: {
          actual_output: string | null
          component_id: string | null
          conclusion: string | null
          created_at: string
          created_by: string | null
          description: string | null
          expected_output: string | null
          experiment_date: string | null
          experiment_objective: string | null
          id: string
          input_values: string | null
          is_published: boolean
          methodology: string | null
          notes: string | null
          operation: string | null
          result_status: Database["public"]["Enums"]["experiment_result"]
          software_used: string
          software_version: string | null
          title: string
          updated_at: string
          updated_by: string | null
        }
        Insert: {
          actual_output?: string | null
          component_id?: string | null
          conclusion?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          expected_output?: string | null
          experiment_date?: string | null
          experiment_objective?: string | null
          id?: string
          input_values?: string | null
          is_published?: boolean
          methodology?: string | null
          notes?: string | null
          operation?: string | null
          result_status?: Database["public"]["Enums"]["experiment_result"]
          software_used?: string
          software_version?: string | null
          title: string
          updated_at?: string
          updated_by?: string | null
        }
        Update: {
          actual_output?: string | null
          component_id?: string | null
          conclusion?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          expected_output?: string | null
          experiment_date?: string | null
          experiment_objective?: string | null
          id?: string
          input_values?: string | null
          is_published?: boolean
          methodology?: string | null
          notes?: string | null
          operation?: string | null
          result_status?: Database["public"]["Enums"]["experiment_result"]
          software_used?: string
          software_version?: string | null
          title?: string
          updated_at?: string
          updated_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "simulations_component_id_fkey"
            columns: ["component_id"]
            isOneToOne: false
            referencedRelation: "project_components"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "simulations_created_by_fkey"
            columns: ["created_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "simulations_updated_by_fkey"
            columns: ["updated_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      technical_documents: {
        Row: {
          component_id: string | null
          created_at: string
          created_by: string | null
          description: string | null
          document_type: Database["public"]["Enums"]["document_type"]
          file_id: string
          id: string
          is_published: boolean
          title: string
          updated_at: string
          version: string
        }
        Insert: {
          component_id?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          document_type: Database["public"]["Enums"]["document_type"]
          file_id: string
          id?: string
          is_published?: boolean
          title: string
          updated_at?: string
          version?: string
        }
        Update: {
          component_id?: string | null
          created_at?: string
          created_by?: string | null
          description?: string | null
          document_type?: Database["public"]["Enums"]["document_type"]
          file_id?: string
          id?: string
          is_published?: boolean
          title?: string
          updated_at?: string
          version?: string
        }
        Relationships: [
          {
            foreignKeyName: "technical_documents_component_id_fkey"
            columns: ["component_id"]
            isOneToOne: false
            referencedRelation: "project_components"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "technical_documents_created_by_fkey"
            columns: ["created_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "technical_documents_file_id_fkey"
            columns: ["file_id"]
            isOneToOne: false
            referencedRelation: "media_files"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      can_edit: {
        Args: never
        Returns: boolean
      }
      can_view_private: {
        Args: never
        Returns: boolean
      }
      current_app_role: {
        Args: never
        Returns: Database["public"]["Enums"]["app_role"]
      }
      is_admin: {
        Args: never
        Returns: boolean
      }
      set_phase_weights: {
        Args: { weights: Json }
        Returns: undefined
      }
    }
    Enums: {
      app_role: "admin" | "editor" | "viewer"
      document_type: "project_report" | "circuit_schematic" | "architecture_document" | "simulation_report" | "datasheet" | "test_report" | "meeting_notes" | "graduation_deliverable"
      experiment_result: "not_started" | "in_progress" | "passed" | "failed" | "needs_review"
      media_category: "simulation_screenshot" | "architecture_diagram" | "circuit_schematic" | "breadboard_photo" | "component_photo" | "testing_evidence" | "report" | "technical_file" | "receipt"
      phase_status: "planned" | "not_started" | "in_progress" | "completed" | "blocked"
      purchase_status: "not_purchased" | "ordered" | "received" | "tested"
      semester: "tasarim_1" | "tasarim_2"
      task_priority: "low" | "medium" | "high"
      work_status: "not_started" | "in_progress" | "completed" | "blocked"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type PublicSchema = Database["public"]
export type Tables<T extends keyof PublicSchema["Tables"]> = PublicSchema["Tables"][T]["Row"]
export type TablesInsert<T extends keyof PublicSchema["Tables"]> = PublicSchema["Tables"][T]["Insert"]
export type TablesUpdate<T extends keyof PublicSchema["Tables"]> = PublicSchema["Tables"][T]["Update"]
export type Enums<T extends keyof PublicSchema["Enums"]> = PublicSchema["Enums"][T]
